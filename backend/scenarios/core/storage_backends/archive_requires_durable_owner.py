import asyncio

from alembic import command
from scenarios.contexts.database_backend import isolated_database_url
from sqlalchemy import text
from vedro import catched, given, scenario, then, when

from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import _get_alembic_config, run_migrations

from ._archive_helpers import ARCHIVES, seed_retry, snapshot


@scenario()
async def empty_archive_storage_without_durable_owner_is_never_adopted():
    async with isolated_database_url() as url:
        with given("correctly-shaped archive tables whose complete ownership records have disappeared"):
            await run_migrations(url)
            await seed_retry(url)
            await asyncio.to_thread(command.downgrade, _get_alembic_config(url), "f6a7b8c9d0e1")
            async with Database(url) as database, database.transaction() as session:
                for table in ARCHIVES:
                    await session.execute(text(f"DELETE FROM {table}"))
            await seed_retry(url, entry_id=9)
            before = await snapshot(url)

        with when("upgrade encounters empty storage with no ownership proof"):
            with catched(RuntimeError) as refused:
                await run_migrations(url)
            after = await snapshot(url)

        with then("it preserves the new live source and refuses to create an implicit owner or acknowledge anything"):
            assert refused.type is RuntimeError
            assert "owner" in str(refused.value)
            assert after == before
