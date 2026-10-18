import asyncio

from alembic import command
from scenarios.contexts.database_backend import isolated_database_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.db.migrations import _get_alembic_config, run_migrations

from ._archive_helpers import ARCHIVES, seed_retry, snapshot, supplied_migration, supplied_snapshot
from .automatic_downgrade_archive import raw_rows

CASES = [
    params(target, kind, direction, False, False)
    for target in ("archive", "webhook_retry_queue", "webhook_dlq")
    for kind in ("table", "view")
    for direction in ("downgrade", "upgrade")
] + [params("archive", "table", "downgrade", True, False), params("archive", "table", "downgrade", False, True)]


@scenario(CASES)
async def supplied_connection_shadows_cannot_capture_or_ack_in_nondurable_relations(
    target, kind, direction, upper, missing
):
    async with isolated_database_url() as url:
        with given("a completed archive cycle and exact raw sources, with an optional pending durable batch"):
            await run_migrations(url)
            await seed_retry(url)
            config = _get_alembic_config(url)
            await asyncio.to_thread(command.downgrade, config, "f6a7b8c9d0e1")
            await run_migrations(url)
            original = await raw_rows(url, "webhook_retry_queue")
            if direction == "upgrade":
                await asyncio.to_thread(command.downgrade, config, "f6a7b8c9d0e1")
            else:
                # Exercise the frozen archive boundary before introducing unsupported TEMP views.
                await asyncio.to_thread(command.downgrade, config, "a7b8c9d0e1f2")
            engine = create_async_engine(url, poolclass=NullPool)

        try:
            async with engine.connect() as connection:
                with given("same-name TEMP tables or views on the actual public Alembic connection"):
                    schema = "main" if connection.dialect.name == "sqlite" else connection.dialect.default_schema_name
                    names = ARCHIVES if target == "archive" else (target,)
                    for name in names:
                        shadow = name.upper() if upper else name
                        qualified = f"{schema}.{name}"
                        if kind == "view":
                            await connection.execute(text(f"CREATE TEMP VIEW {shadow} AS SELECT * FROM {qualified}"))
                        elif connection.dialect.name == "sqlite":
                            await connection.execute(text(f"CREATE TEMP TABLE {shadow} AS SELECT * FROM {qualified}"))
                        else:
                            await connection.execute(
                                text(f"CREATE TEMP TABLE {shadow} (LIKE {qualified} INCLUDING ALL)")
                            )
                            if target != "archive":
                                await connection.execute(
                                    text(f"INSERT INTO pg_temp.{shadow} SELECT * FROM {qualified}")
                                )
                    if missing:
                        for name in ARCHIVES:
                            await connection.execute(text(f"DROP TABLE {schema}.{name}"))
                    await connection.commit()
                    before = await supplied_snapshot(url, connection)
                    await connection.rollback()

                with when("migration is invoked with this exact supplied connection"):
                    with catched(RuntimeError) as refused:
                        await supplied_migration(url, connection, direction)
                    after = await supplied_snapshot(url, connection)

                with then("all durable and TEMP state is preserved before any mutation or acknowledgment"):
                    assert refused.type is RuntimeError
                    assert "persistent relation" in str(refused.value)
                    assert after == before
        finally:
            await engine.dispose()

        with when("the physical connection is closed and a normal connection completes the real migration"):
            if direction == "downgrade":
                await asyncio.to_thread(command.downgrade, config, "f6a7b8c9d0e1")
            await run_migrations(url)
            restored = await raw_rows(url, "webhook_retry_queue")
            reopened = await snapshot(url)
            pending = [
                [row for row in reopened[name]["rows"] if row["archive_id"] != "__contract_v1__"] for name in ARCHIVES
            ]

        with then("source data survives reopening exactly and only the durable archive is acknowledged"):
            assert restored == original
            assert pending == [[], [], []]
