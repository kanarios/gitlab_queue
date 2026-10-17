import asyncio

from alembic import command
from scenarios.contexts.database_backend import isolated_database_url
from sqlalchemy import text
from vedro import given, scenario, then, when

from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import _get_alembic_config, get_current_revision, run_migrations
from gitlab_queue.webhooks.retry_manager import WebhookRetryManager

from .nullable_retry_timestamps import authenticated_dlq_client


async def raw_rows(database_url, table):
    async with Database(database_url) as database, database.session() as session:
        return [dict(row) for row in (await session.execute(text(f"SELECT * FROM {table} ORDER BY id"))).mappings()]


@scenario()
async def installed_a7_automatically_archives_and_restores_unknown_retry_dates():
    async with isolated_database_url() as database_url:
        with given("an already-installed a7 containing unknown dates, raw JSON and compatible foreign-project rows"):
            await run_migrations(database_url)
            payload = ' {"duplicate": 1, "duplicate": 2, "unicode": "ёж", "nested": [null, true]} '
            async with Database(database_url) as database, database.transaction() as session:
                for entry_id, project_id, created_at in ((7, 123, None), (8, 456, "2000-01-01T12:00:00.123456+05:00")):
                    await session.execute(
                        text(
                            "INSERT INTO webhook_retry_queue "
                            "(id, project_id, event_type, payload, attempt_count, max_attempts, next_attempt_at, last_error, created_at) "
                            "VALUES (:id, :project, 'merge_request', :payload, 4, 7, :due, 'exact error', :created)"
                        ),
                        {
                            "id": entry_id,
                            "project": project_id,
                            "payload": payload,
                            "due": "2000-01-01 00:00:00",
                            "created": created_at,
                        },
                    )
                for entry_id, project_id, original, moved in (
                    (4, 123, None, "2026-10-16T23:15:00.123456+05:00"),
                    (5, 123, "2000-01-01 00:00:00", None),
                    (6, 456, "2000-01-01 00:00:00", "2026-10-16T23:15:00.123456+05:00"),
                ):
                    await session.execute(
                        text(
                            "INSERT INTO webhook_dlq "
                            "(id, project_id, event_type, payload, attempt_count, last_error, original_created_at, moved_to_dlq_at) "
                            "VALUES (:id, :project, 'merge_request', :payload, 7, 'original failure', :original, :moved)"
                        ),
                        {
                            "id": entry_id,
                            "project": project_id,
                            "payload": payload,
                            "original": original,
                            "moved": moved,
                        },
                    )
            before_retry = await raw_rows(database_url, "webhook_retry_queue")
            before_dead = await raw_rows(database_url, "webhook_dlq")

        with when("public Alembic directly downgrades a7 to f6, then startup upgrades and reopens it"):
            await asyncio.to_thread(command.downgrade, _get_alembic_config(database_url), "f6a7b8c9d0e1")
            downgraded = await get_current_revision(database_url)
            old_retry = await raw_rows(database_url, "webhook_retry_queue")
            old_dead = await raw_rows(database_url, "webhook_dlq")
            await run_migrations(database_url)
            restored_retry = await raw_rows(database_url, "webhook_retry_queue")
            restored_dead = await raw_rows(database_url, "webhook_dlq")
            async with Database(database_url) as database:
                manager = WebhookRetryManager(database)
                ready = await manager.get_events_ready_for_retry(project_id=123)
                async with authenticated_dlq_client(database, manager) as client:
                    listing = await client.get("/api/dlq")
                    detail = await client.get("/api/dlq/4")

        with then("raw values and original identities return without requeueing or fabricated timestamps"):
            assert downgraded == "f6a7b8c9d0e1"
            assert old_retry == [before_retry[1]]
            assert old_dead == [before_dead[2]]
            assert restored_retry == before_retry
            assert restored_dead == before_dead
            assert ready[0].id == 7
            assert ready[0].attempt_count == 4
            assert ready[0].max_attempts == 7
            assert ready[0].created_at is None
            assert listing.status_code == detail.status_code == 200
            assert detail.json()["original_created_at"] is None
