import asyncio
from datetime import UTC, datetime

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from sqlalchemy import text
from vedro import given, params, scenario, then, when

from gitlab_queue.core.processor import create_processor
from gitlab_queue.db.migrations import run_migrations

from ._helpers import queue_environment


@scenario(
    [
        params("poll", "head"),
        params("startup", "head"),
        params("poll", "d4e5f6a7b8c9"),
        params("startup", "d4e5f6a7b8c9"),
    ]
)
async def sync_preserves_recreated_entry(entrypoint, initial_revision):
    async with queue_environment(initial_revision) as env:
        with given("an old sync snapshot of an ordinary queue entry"):
            # Emulate the deployed old writer without requiring the current
            # QueueManager's newly added columns in the previous schema.
            async with env.queue.db.transaction() as session:
                await session.execute(
                    text(
                        "INSERT INTO merge_requests (project_id, iid, title, author_name, author_username, "
                        "target_branch, status, is_hotfix, labels, queued_at) "
                        "VALUES (123, :iid, 'Old entry', 'Author', 'author', 'main', 'queued', 0, "
                        "'[\"merge_queue\"]', :queued_at)"
                    ),
                    [{"iid": iid, "queued_at": datetime.now(UTC).isoformat()} for iid in (1, 3)],
                )
            await env.queue.db.close()
            await run_migrations(env.queue.db.database_url)
            await env.queue.db.initialize()
            env.server.mrs = [mr_response(1, labels=["merge_queue"]), mr_response(3, labels=["merge_queue"])]
            entered, release = asyncio.Event(), asyncio.Event()
            env.server.barriers[("GET", "merge_queue")] = (entered, release)
            processor = create_processor(
                env.gitlab,
                env.queue,
                env.handler.notifier,
                env.settings,
                position_notifier=env.handler.position_notifier,
            )
            processor.request_shutdown()
            sync = {"poll": env.scheduler.sync_queue, "startup": processor.run}[entrypoint]

        with when("the old entry is removed and recreated as a hotfix before sync finishes"):
            task = asyncio.create_task(sync())
            await asyncio.wait_for(entered.wait(), 5)
            await env.queue.remove_from_queue(123, 3)
            await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue", "hotfix"]), is_hotfix=True)
            release.set()
            await asyncio.wait_for(task, 5)

        with then("the snapshot of the old incarnation cannot demote the replacement"):
            next_mr = await env.queue.get_next_mr(123)
            assert next_mr.mr_iid == 3
            assert next_mr.is_hotfix is True
            assert env.server.comments == []
