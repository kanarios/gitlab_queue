from contextlib import asynccontextmanager

from scenarios.contexts.database_backend import isolated_database_url

from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import run_migrations


@asynccontextmanager
async def migrated_storage():
    async with isolated_database_url() as database_url:
        await run_migrations(database_url)
        async with Database(database_url) as database:
            yield database
