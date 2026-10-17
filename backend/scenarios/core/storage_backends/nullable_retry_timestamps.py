import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
from alembic import command
from scenarios.contexts.api_helpers import created_mock_health, created_test_jwt
from scenarios.contexts.database_backend import isolated_database_url
from scenarios.core.hotfix_priority._helpers import GitLabServer, queue_services
from sqlalchemy import null, text
from vedro import given, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import _get_alembic_config, get_current_revision, run_migrations
from gitlab_queue.db.models import WebhookDLQModel, WebhookRetryModel
from gitlab_queue.webhooks.retry_manager import WebhookRetryManager
from gitlab_queue.webhooks.router import WebhookAppState, create_webhook_app


@asynccontextmanager
async def authenticated_dlq_client(database, manager):
    async with queue_services(QueueManager(database), GitLabServer()) as env:
        app = create_webhook_app(
            WebhookAppState(
                env.settings,
                database,
                env.gitlab,
                env.queue,
                env.handler.notifier,
                env.handler.position_notifier,
                manager,
                created_mock_health(),
                env.websocket,
            )
        )
        headers = {"Authorization": f"Bearer {created_test_jwt(env.settings, project_id=123)}"}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test", headers=headers
        ) as client:
            yield client


@scenario()
async def legacy_unknown_retry_creation_survives_dlq_and_requeue():
    async with isolated_database_url() as database_url:
        with given("a previous-schema retry batch with known and unknown original receipt times"):
            await run_migrations(database_url)
            await asyncio.to_thread(command.downgrade, _get_alembic_config(database_url), "f6a7b8c9d0e1")
            known_at = datetime.now(UTC) - timedelta(days=1)
            payload = {"project": {"id": 123}, "unicode": "ёж", "_queue_webhook": {"message_id": "unknown"}}
            async with Database(database_url) as database, database.transaction() as session:
                unknown = WebhookRetryModel(
                    project_id=123,
                    event_type="merge_request",
                    payload=json.dumps(payload),
                    max_attempts=1,
                    next_attempt_at=known_at.isoformat(),
                    created_at=null(),
                )
                known = WebhookRetryModel(
                    project_id=123,
                    event_type="merge_request",
                    payload="{}",
                    next_attempt_at=known_at.isoformat(),
                    created_at=known_at.isoformat(),
                )
                session.add_all([unknown, known])
                await session.flush()
                source, known_source = unknown.id, known.id

        with when("startup upgrades, reads the batch, exhausts the unknown event and the API requeues it"):
            await run_migrations(database_url)
            async with Database(database_url) as database:
                manager = WebhookRetryManager(database, max_attempts=1, base_delay_seconds=0)
                ready = await manager.get_events_ready_for_retry(project_id=123)
                await manager.mark_retry_success(known_source, 123)
                await manager.mark_retry_failed(source, "final", 123)
                async with authenticated_dlq_client(database, manager) as client:
                    listing = await client.get("/api/dlq")
                    entry_id = listing.json()["items"][0]["id"]
                    detail = await client.get(f"/api/dlq/{entry_id}")
                    replay = await client.post(f"/api/dlq/{entry_id}/retry")
                replacement = (await manager.get_events_ready_for_retry(project_id=123))[0]

        with then("unknown provenance stays null while known dates and the new receipt remain truthful"):
            assert [item.id for item in ready] == [source, known_source]
            assert ready[0].created_at is None
            assert ready[1].created_at == known_at
            assert listing.status_code == detail.status_code == replay.status_code == 200
            assert listing.json()["items"][0]["original_created_at"] is None
            assert detail.json()["original_created_at"] is None
            assert detail.json()["moved_to_dlq_at"] is not None
            assert replacement.id == replay.json()["retry_id"]
            assert replacement.id > source
            assert replacement.created_at is not None
            assert replacement.payload == payload
            assert replacement.project_id == 123
            assert replacement.attempt_count == 0


@scenario()
async def legacy_missing_dlq_move_time_and_literal_creation_remain_unknown():
    async with isolated_database_url() as database_url:
        with given("a previous-schema DLQ entry with a missing move time and a literal timestamp elsewhere"):
            await run_migrations(database_url)
            await asyncio.to_thread(command.downgrade, _get_alembic_config(database_url), "f6a7b8c9d0e1")
            original_at = "2026-10-16T23:15:00.123456+05:00"
            async with Database(database_url) as database, database.transaction() as session:
                dead = WebhookDLQModel(
                    project_id=123,
                    event_type="merge_request",
                    payload="{}",
                    attempt_count=1,
                    last_error="legacy",
                    original_created_at=original_at,
                    moved_to_dlq_at=null(),
                )
                session.add_all(
                    [
                        dead,
                        WebhookRetryModel(
                            project_id=123,
                            event_type="merge_request",
                            payload="{}",
                            next_attempt_at="2000-01-01 00:00:00",
                            created_at="CURRENT_TIMESTAMP",
                        ),
                    ]
                )
                await session.flush()
                dead_id = dead.id

        with when("migration preserves raw unknown dates and authenticated list/detail read the reopened database"):
            await run_migrations(database_url)
            async with Database(database_url) as database:
                manager = WebhookRetryManager(database)
                repaired_retry = (await manager.get_events_ready_for_retry(project_id=123))[0]
                repaired_dead = await manager.get_dlq_entry(dead_id, 123)
                async with database.session() as session:
                    raw_date = (
                        await session.execute(text("SELECT created_at FROM webhook_retry_queue WHERE project_id = 123"))
                    ).scalar_one()
                    await session.commit()
                async with authenticated_dlq_client(database, manager) as client:
                    listing = await client.get("/api/dlq")
                    detail = await client.get(f"/api/dlq/{dead_id}")

        with then("no original or move date is fabricated and public readers remain usable"):
            assert repaired_dead.moved_to_dlq_at is None
            assert repaired_retry.created_at is None
            assert raw_date == "CURRENT_TIMESTAMP"
            assert repaired_dead.original_created_at == datetime.fromisoformat(original_at)
            assert listing.status_code == detail.status_code == 200
            assert detail.json()["moved_to_dlq_at"] is None


@scenario()
async def downgrade_archives_unknown_original_dates_without_redelivery():
    async with isolated_database_url() as database_url:
        with given("a current-schema DLQ row whose original receipt date is unknown"):
            await run_migrations(database_url)
            async with Database(database_url) as database, database.transaction() as session:
                dead = WebhookDLQModel(
                    project_id=123,
                    event_type="merge_request",
                    payload='{"unknown": true}',
                    attempt_count=1,
                    last_error="legacy",
                    original_created_at=null(),
                )
                session.add(dead)
                await session.flush()
                dead_id = dead.id

        with when("downgrade archives unrepresentable rows and upgrade automatically restores them"):
            config = _get_alembic_config(database_url)
            await asyncio.to_thread(command.downgrade, config, "f6a7b8c9d0e1")
            current = await get_current_revision(database_url)
            async with Database(database_url) as database:
                manager = WebhookRetryManager(database, base_delay_seconds=0)
                archived = await manager.get_dlq_entries(project_id=123)
            await run_migrations(database_url)
            async with Database(database_url) as database:
                manager = WebhookRetryManager(database)
                preserved = await manager.get_dlq_entry(dead_id, 123)
                retry = await manager.get_events_ready_for_retry(project_id=123)

        with then("the same DLQ entry returns without resetting attempts or scheduling a new delivery"):
            assert current == "f6a7b8c9d0e1"
            assert archived == []
            assert preserved.id == dead_id
            assert preserved.original_created_at is None
            assert preserved.payload == {"unknown": True}
            assert preserved.attempt_count == 1
            assert preserved.last_error == "legacy"
            assert retry == []
