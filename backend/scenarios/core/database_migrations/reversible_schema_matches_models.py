import asyncio

from alembic import command
from alembic.script import ScriptDirectory
from scenarios.contexts.database_backend import isolated_database_url
from sqlalchemy import inspect
from vedro import given, scenario, then, when

from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import _get_alembic_config, get_current_revision, run_migrations


@scenario()
async def reversible_schema_matches_models():
    async with isolated_database_url() as database_url:
        with given("a fresh isolated database upgraded using the deployment migration runner"):
            await run_migrations(database_url)
            config = _get_alembic_config(database_url)
            heads = ScriptDirectory.from_config(config).get_heads()
            await asyncio.to_thread(command.check, config)

        with when("all migrations are reversed and reapplied"):
            await asyncio.to_thread(command.downgrade, config, "base")
            async with Database(database_url) as database, database.engine.connect() as connection:
                remaining = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
            await run_migrations(database_url)
            await asyncio.to_thread(command.check, config)
            current = await get_current_revision(database_url)
            async with Database(database_url) as database:
                health = await database.health_check()

        with then("the only migration head is restored without model drift or leftover application tables"):
            assert heads == ["a7b8c9d0e1f2"]
            assert remaining == ["alembic_version"]
            assert current == heads[0]
            assert health.connected is True
            assert health.foreign_keys_enabled is True
            assert health.error is None
