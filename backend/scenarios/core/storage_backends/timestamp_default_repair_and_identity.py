import asyncio
from datetime import UTC, datetime, timedelta

from alembic import command
from scenarios.contexts.database_backend import isolated_database_url
from scenarios.fakes import create_mr
from scenarios.integration.repositories._helpers import create_test_history_model, create_test_mr_model
from sqlalchemy import inspect, null, text
from vedro import given, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import _get_alembic_config, run_migrations
from gitlab_queue.db.models import WebhookDLQModel, WebhookRetryModel
from gitlab_queue.db.repositories import HistoryRepository, MergeRequestRepository
from gitlab_queue.webhooks.retry_manager import WebhookRetryManager


@scenario()
async def timestamp_defaults_and_identity_preserve_legacy_data_without_rewriting_retry_dates():
    async with isolated_database_url() as database_url:
        with given("the previous schema with literal defaults, valid offsets, optional NULL and deleted high IDs"):
            await run_migrations(database_url)
            await asyncio.to_thread(command.downgrade, _get_alembic_config(database_url), "f6a7b8c9d0e1")
            valid = "2026-10-16T23:15:00.123456+05:00"
            async with Database(database_url) as database:
                queue = QueueManager(database)
                await queue.add_to_queue(123, create_mr(iid=1))
                removed = await queue.add_to_queue(123, create_mr(iid=2))
                await queue.complete_mr(123, 2, "merged")
                manager = WebhookRetryManager(database, max_attempts=1, base_delay_seconds=0)
                async with database.transaction() as session:
                    bad_retry = WebhookRetryModel(
                        project_id=123,
                        event_type="merge_request",
                        payload="{}",
                        next_attempt_at=valid,
                        created_at="CURRENT_TIMESTAMP",
                    )
                    optional = WebhookRetryModel(
                        project_id=999,
                        event_type="merge_request",
                        payload="{}",
                        next_attempt_at=valid,
                        created_at=null(),
                    )
                    bad_dead = WebhookDLQModel(
                        project_id=123,
                        event_type="legacy",
                        payload="{}",
                        attempt_count=1,
                        last_error="legacy",
                        original_created_at="CURRENT_TIMESTAMP",
                    )
                    old_history = create_test_history_model(
                        iid=99, finished_at=(datetime.now(UTC) - timedelta(days=400)).isoformat()
                    )
                    old_history.project_id = 123
                    session.add_all([bad_retry, optional, bad_dead, old_history])
                    valid_mr = create_test_mr_model(iid=9)
                    valid_mr.created_at = valid
                    await MergeRequestRepository(session, project_id=202).add(valid_mr)
                    await session.flush()
                    history_high = old_history.id
                source = await manager.add_to_retry_queue("merge_request", {"project": {"id": 123}}, "temporary", 123)
                await manager.mark_retry_failed(source, "final", 123)
                dead_high = max(
                    entry.id for entry in await manager.get_dlq_entries(project_id=123, event_type="merge_request")
                )
                # The bad legacy entry is not parsed until migration repairs it.
                await manager.delete_dlq_entry(dead_high, 123)
                retry_high = await manager.add_to_retry_queue("merge_request", {}, "temporary", 123)
                await manager.mark_retry_success(retry_high, 123)
                async with database.transaction() as session:
                    await HistoryRepository(session, project_id=123).cleanup_old_records()
            before = datetime.now(UTC)

        with when("head repairs legacy defaults and the database is reopened"):
            await run_migrations(database_url)
            after = datetime.now(UTC)
            async with Database(database_url) as database:
                queue, manager = (
                    QueueManager(database),
                    WebhookRetryManager(database, max_attempts=1, base_delay_seconds=0),
                )
                async with database.session() as session:
                    repaired = [
                        (
                            await session.execute(
                                text(f"SELECT {column} FROM {table} WHERE project_id = 123 ORDER BY id LIMIT 1")
                            )
                        ).scalar_one()
                        for table, column in (
                            ("merge_requests", "created_at"),
                            ("merge_requests_history", "created_at"),
                        )
                    ]
                    preserved_valid = (
                        await session.execute(text("SELECT created_at FROM merge_requests WHERE project_id = 202"))
                    ).scalar_one()
                    preserved_null = (
                        await session.execute(text("SELECT created_at FROM webhook_retry_queue WHERE project_id = 999"))
                    ).scalar_one()
                    raw_retry_date = (
                        await session.execute(
                            text(
                                "SELECT created_at FROM webhook_retry_queue WHERE project_id = 123 ORDER BY id LIMIT 1"
                            )
                        )
                    ).scalar_one()
                    raw_dead_dates = (
                        await session.execute(
                            text(
                                "SELECT original_created_at, moved_to_dlq_at FROM webhook_dlq WHERE project_id = 123 ORDER BY id LIMIT 1"
                            )
                        )
                    ).one()
                    await session.commit()
                async with database.engine.connect() as connection:
                    defaults = await connection.run_sync(
                        lambda sync: [
                            next(
                                column["default"]
                                for column in inspect(sync).get_columns(table)
                                if column["name"] == name
                            )
                            for table, name in (
                                ("merge_requests", "created_at"),
                                ("merge_requests_history", "created_at"),
                                ("webhook_retry_queue", "created_at"),
                                ("webhook_dlq", "moved_to_dlq_at"),
                            )
                        ]
                    )
                new_queue = await queue.add_to_queue(123, create_mr(iid=3))
                new_retry = await manager.add_to_retry_queue("merge_request", {}, "new", 123)
                await manager.mark_retry_failed(new_retry, "final", 123)
                new_dead = max(entry.id for entry in await manager.get_dlq_entries(project_id=123))
                await queue.complete_mr(123, 3, "merged")
                new_history = (await queue.get_recent_history(project_id=123))[0].queue_id

        with then(
            "one conservative repair instant replaces literals without losing valid data or identity high-water marks"
        ):
            assert len(set(repaired)) == 1
            assert before <= datetime.fromisoformat(repaired[0]) <= after
            assert preserved_valid == valid
            assert preserved_null is None
            assert raw_retry_date == "CURRENT_TIMESTAMP"
            assert tuple(raw_dead_dates) == ("CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
            assert all("'CURRENT_TIMESTAMP'" not in default for default in defaults)
            assert new_queue.queue_id > removed.queue_id
            assert new_retry > retry_high
            assert new_dead > dead_high
            assert new_history > history_high
