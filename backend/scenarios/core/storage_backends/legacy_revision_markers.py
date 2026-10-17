import asyncio
import os
from contextlib import contextmanager

from alembic import command
from scenarios.contexts.database_backend import isolated_database_url
from scenarios.fakes import create_mr
from sqlalchemy import text
from vedro import given, params, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import (
    _get_alembic_config,
    _stamp_legacy_database_if_needed,
    get_current_revision,
    run_migrations,
)


@contextmanager
def legacy_project_owner():
    names = ("GITLAB_QUEUE_GITLAB_PROJECT_ID", "GITLAB_QUEUE_PROJECTS")
    previous = {name: os.environ.get(name) for name in names}
    os.environ["GITLAB_QUEUE_GITLAB_PROJECT_ID"] = "123"
    os.environ["GITLAB_QUEUE_PROJECTS"] = ""
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@scenario(
    [
        params("34c99f29b96d"),
        params("a312c27ba5f7"),
        params("b8c5a3f12e47"),
        params("d61e3097360d"),
        params("c754365eda26"),
        params("e9a1b2c3d4f5"),
        params("f1a2b3c4d5e6"),
    ]
)
async def legacy_revision_markers_preserve_populated_queue_on_upgrade(revision):
    with legacy_project_owner():
        async with isolated_database_url() as database_url:
            with given("a populated historic schema whose pre-Alembic version marker is absent"):
                await run_migrations(database_url)
                async with Database(database_url) as database:
                    original = await QueueManager(database).add_to_queue(123, create_mr(iid=3))
                config = _get_alembic_config(database_url)
                await asyncio.to_thread(command.downgrade, config, revision)
                async with Database(database_url) as database, database.engine.begin() as connection:
                    await connection.execute(text("DROP TABLE alembic_version"))

            with when("legacy detection stamps its actual marker and concurrent startups upgrade it"):
                stamped = await _stamp_legacy_database_if_needed(database_url)
                detected = await get_current_revision(database_url)
                upgraded = await asyncio.gather(run_migrations(database_url), run_migrations(database_url))
                current_revision = await get_current_revision(database_url)
                async with Database(database_url) as database:
                    current = await QueueManager(database).get_queue_item(123, 3)

            with then("the precise baseline is recognized and one startup owns the data-preserving upgrade"):
                assert stamped is True
                assert detected == revision
                assert sorted(upgraded) == [False, True]
                assert current_revision == "a7b8c9d0e1f2"
                assert current.queue_id == original.queue_id
                assert current.queued_at == original.queued_at
                assert current.state == original.state
