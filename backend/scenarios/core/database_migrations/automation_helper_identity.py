from scenarios.contexts.database_backend import isolated_database_url
from scenarios.fakes import create_mr
from vedro import given, params, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import run_migrations


@scenario([params([2]), params([1, 2])])
async def current_schema_helper_keeps_deleted_queue_identity_through_legacy_stamp(completed):
    async with isolated_database_url() as url:
        with given("the current schema helper with a deleted highest queue ID before its first Alembic stamp"):
            async with Database(url) as database:
                queue = QueueManager(database)
                await queue.ensure_schema()
                await queue.ensure_schema()
                await queue.add_to_queue(123, create_mr(iid=1))
                highest = await queue.add_to_queue(123, create_mr(iid=2))
                for iid in completed:
                    await queue.complete_mr(123, iid, "merged")

        with when("startup stamps, upgrades and reopens that real helper-created schema"):
            await run_migrations(url)
            async with Database(url) as database:
                queue = QueueManager(database)
                replacement = await queue.add_to_queue(123, create_mr(iid=3))
                history = await queue.get_recent_history(project_id=123)

        with then("a new incarnation cannot reuse any completed ID"):
            assert replacement.queue_id > highest.queue_id
            assert replacement.is_automated is False
            assert len(history) == len(completed)
