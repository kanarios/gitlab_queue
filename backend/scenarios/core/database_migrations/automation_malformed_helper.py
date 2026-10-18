from scenarios.contexts.database_backend import isolated_database_url
from scenarios.core.storage_backends._archive_helpers import snapshot
from sqlalchemy import text
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import run_migrations


@scenario([params("INTEGER DEFAULT 0"), params("TEXT NOT NULL DEFAULT '0'"), params("INTEGER NOT NULL DEFAULT 1")])
async def malformed_existing_automation_column_is_refused_before_legacy_stamp(definition):
    async with isolated_database_url() as url:
        with given("an unversioned helper schema with a noncanonical preexisting automation column"):
            async with Database(url) as database:
                await QueueManager(database).ensure_schema()
                async with database.transaction() as session:
                    await session.execute(text("ALTER TABLE merge_requests DROP COLUMN is_automated"))
                    await session.execute(text(f"ALTER TABLE merge_requests ADD COLUMN is_automated {definition}"))
            before = await snapshot(url, include_sequences=True)

        with when("the public startup migration runner examines the helper schema"):
            with catched(RuntimeError) as error:
                await run_migrations(url)
            after = await snapshot(url, include_sequences=True)

        with then("no version stamp, schema mutation, archive ownership or sequence change is accepted"):
            assert error.type is RuntimeError
            assert after == before
