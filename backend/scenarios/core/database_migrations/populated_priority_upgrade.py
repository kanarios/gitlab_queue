import asyncio
import json
from datetime import UTC, datetime, timedelta

from alembic import command
from scenarios.contexts.database_backend import isolated_database_url
from scenarios.fakes import create_mr
from sqlalchemy import text
from vedro import given, params, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import _get_alembic_config, run_migrations
from gitlab_queue.models.completion import CompletionRequest


async def snapshot(database_url):
    async with Database(database_url) as database, database.session() as session:
        queue = await session.execute(text("SELECT * FROM merge_requests ORDER BY id"))
        history = await session.execute(text("SELECT * FROM merge_requests_history ORDER BY id"))
        result = ([dict(row) for row in queue.mappings()], [dict(row) for row in history.mappings()])
        await session.commit()
        return result


@scenario([params("c3d7f1a8b902"), params("d4e5f6a7b8c9"), params("e5f6a7b8c9d0")])
async def populated_priority_upgrade(previous_revision):
    async with isolated_database_url() as database_url:
        with given("populated previous-schema queue and history records in two projects"):
            await run_migrations(database_url)
            async with Database(database_url) as database:
                queue = QueueManager(database)
                await queue.add_to_queue(123, create_mr(iid=3))
                await queue.add_to_queue(202, create_mr(iid=3, title="Other project"))
                await queue.update_hotfix_status(123, 3, True, ["merge_queue", "hotfix"], notify_positions=True)
                await queue.update_mr_state(123, 3, "rebasing", pipeline_id=101, processing_attempts=2)
                await queue.add_to_queue(123, create_mr(iid=4))
                await queue.complete_mr(123, 4, "merged")
                owner = await queue.add_to_queue(123, create_mr(iid=5))
                await queue.prepare_completion(
                    123,
                    5,
                    CompletionRequest(
                        "failed",
                        "conflict",
                        "conflict",
                        {"failed_at": datetime.now(UTC)},
                        "conflict",
                        queue_id=owner.queue_id,
                    ),
                )
                await queue.defer_requeue(
                    123,
                    owner,
                    {
                        "is_hotfix": True,
                        "labels": ["hotfix"],
                        "triggers": ["hotfix"],
                        "requested_at": (datetime.now(UTC) + timedelta(seconds=1)).isoformat(),
                        "message_id": "migration-request",
                    },
                )
                payload = json.loads((await queue.get_queue_item(123, 5)).pending_completion)
                payload["label_events"] = ["operation:cleanup", "admission:consumed"]
                await queue.save_completion_progress(123, owner.queue_id, payload)
            config = _get_alembic_config(database_url)
            await asyncio.to_thread(command.downgrade, config, previous_revision)
            before_queue, before_history = await snapshot(database_url)

        with when("the deployed Alembic upgrade reaches head"):
            await run_migrations(database_url)
            after_queue, after_history = await snapshot(database_url)

        with then("all existing columns, identities, workflow values and project records survive"):
            assert [
                {key: after[key] for key in before} for before, after in zip(before_queue, after_queue, strict=True)
            ] == before_queue
            assert [
                {key: after[key] for key in before} for before, after in zip(before_history, after_history, strict=True)
            ] == before_history
            assert [(row["project_id"], row["iid"]) for row in after_queue] == [(123, 3), (202, 3), (123, 5)]
            assert after_queue[0]["pipeline_id"] == 101
            assert after_queue[0]["processing_attempts"] == 2
            assert after_queue[0]["is_hotfix"] == 1
            assert len(after_history) == 1
            assert after_history[0]["status"] == "merged"
