import asyncio
import json
from datetime import UTC, datetime

from alembic import command
from scenarios.contexts.database_backend import isolated_database_url
from scenarios.core.storage_backends._archive_helpers import observed_migration, seed_dead, seed_retry, snapshot
from scenarios.fakes import create_mr
from sqlalchemy import text
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.config import ProjectConfig, Secret
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import _get_alembic_config, run_migrations
from gitlab_queue.models.completion import CompletionRequest


async def queue_rows(url):
    async with Database(url) as database, database.session() as session:
        rows = (await session.execute(text("SELECT * FROM merge_requests ORDER BY id"))).mappings().all()
        await session.commit()
        return [dict(row) for row in rows]


@scenario()
async def automation_downgrade_reupgrade_preserves_raw_lifecycle_and_deleted_high_water():
    async with isolated_database_url() as url:
        with given("active automation, a frozen completion and a deleted highest queue ID"):
            await run_migrations(url)
            policy = ProjectConfig(123, Secret("test"), automation_labels=("dependencies",))
            async with Database(url) as database:
                queue = QueueManager(database, project_policies={123: policy})
                await queue.add_to_queue(123, create_mr(iid=1, labels=["merge_queue", "dependencies"]))
                owned = await queue.add_to_queue(123, create_mr(iid=3, labels=["hotfix", "dependencies"]))
                await queue.update_mr_state(123, 3, "rebasing", pipeline_id=101, expected_sha="original-sha")
                await queue.prepare_completion(
                    123,
                    3,
                    CompletionRequest(
                        "failed", "failed", "conflict", {"failed_at": datetime.now(UTC)}, queue_id=owned.queue_id
                    ),
                )
                await queue.defer_requeue(
                    123,
                    owned,
                    {
                        "triggers": ["hotfix"],
                        "labels": ["hotfix", "dependencies"],
                        "is_hotfix": True,
                        "requested_at": None,
                    },
                )
                await QueueManager(database).add_to_queue(456, create_mr(iid=1))
                highest = await queue.add_to_queue(123, create_mr(iid=99))
                await queue.complete_mr(123, 99, "merged")
            before = [
                {key: value for key, value in row.items() if key != "is_automated"} for row in await queue_rows(url)
            ]
            config = _get_alembic_config(url)

        with when("two supported new-to-a7-to-new cycles reopen and activate the policy"):
            for _ in range(2):
                await asyncio.to_thread(command.downgrade, config, "a7b8c9d0e1f2")
                await run_migrations(url)
            async with Database(url) as database:
                queue = QueueManager(database, project_policies={123: policy})
                await queue.activate_priorities(123)
                active = await queue.get_queue_item(123, 1)
                owned_after = await queue.get_queue_item(123, 3)
                after = [
                    {
                        key: value
                        for key, value in row.items()
                        if key not in ("is_automated", "metadata_version", "pending_notification")
                    }
                    for row in await queue_rows(url)
                ]
                replacement = await queue.add_to_queue(123, create_mr(iid=5))

        with then("only the new active fact is rebuilt and old identity, outcome and raw requests survive"):
            assert after == [
                {key: value for key, value in row.items() if key not in ("metadata_version", "pending_notification")}
                for row in before
            ]
            assert active.priority == "automated"
            assert owned_after.pending_completion == before[1]["pending_completion"]
            assert owned_after.requeue_request == before[1]["requeue_request"]
            assert "is_automated" not in json.loads(owned_after.pending_completion)["history"]
            assert replacement.queue_id > highest.queue_id


@scenario([params("upgrade"), params("downgrade")])
async def automation_ddl_and_version_are_one_physical_transaction(direction):
    async with isolated_database_url() as url:
        with given("a populated queue immediately before the new additive or reversal boundary"):
            await run_migrations(url)
            async with Database(url) as database:
                queue = QueueManager(database)
                await queue.add_to_queue(123, create_mr(iid=1))
                highest = await queue.add_to_queue(123, create_mr(iid=2))
                await queue.complete_mr(123, 2, "merged")
            if direction == "upgrade":
                await asyncio.to_thread(command.downgrade, _get_alembic_config(url), "a7b8c9d0e1f2")
            before = await snapshot(url, include_sequences=True)

        with when("the supplied physical connection raises after the first revision update following DDL"):
            with catched(RuntimeError) as error:
                await observed_migration(
                    url,
                    direction,
                    "version",
                    version_target={"upgrade": "b8c9d0e1f2a3", "downgrade": "a7b8c9d0e1f2"}[direction],
                )
            after = await snapshot(url, include_sequences=True)
            await run_migrations(url)
            async with Database(url) as database:
                replacement = await QueueManager(database).add_to_queue(123, create_mr(iid=3))

        with then("schema, raw rows, revision and high-water roll back together and healthy replay works"):
            assert error.type is RuntimeError
            assert str(error.value) == "injected migration interruption"
            assert after == before
            assert replacement.queue_id > highest.queue_id


@scenario()
async def new_revision_keeps_the_frozen_retry_archive_roundtrip_contract():
    async with isolated_database_url() as url:
        with given("unknown-date retry and DLQ raw payloads under the new head"):
            await run_migrations(url)
            await seed_retry(url)
            await seed_dead(url)
            before = await snapshot(url, include_sequences=True)

        with when("rollback crosses a7 and its frozen archive boundary before returning to the new revision"):
            await asyncio.to_thread(command.downgrade, _get_alembic_config(url), "f6a7b8c9d0e1")
            await run_migrations(url)
            after = await snapshot(url, include_sequences=True)

        with then("raw retry/DLQ columns, IDs, project, JSON text, unknown dates and sequences remain exact"):
            assert after["webhook_retry_queue"] == before["webhook_retry_queue"]
            assert after["webhook_dlq"] == before["webhook_dlq"]
            assert after["alembic_version"] == before["alembic_version"]
