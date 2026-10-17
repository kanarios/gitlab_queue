import asyncio

from alembic import command
from scenarios.contexts.database_backend import isolated_database_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import _get_alembic_config, run_migrations

from ._archive_helpers import ARCHIVES, seed_dead, seed_retry, snapshot, supplied_migration, supplied_snapshot
from .archive_mutation_safety import TARGETS
from .automatic_downgrade_archive import raw_rows


def reference_name(target, style):
    if style == "upper":
        return target.upper()
    return "".join(char.upper() if index % 2 else char for index, char in enumerate(target))


async def prepared_owned_sources(url, target):
    await run_migrations(url)
    await seed_retry(url)
    await seed_retry(url, entry_id=8, project_id=456, created_at="2000-01-01")
    await seed_dead(url)
    original = {name: await raw_rows(url, name) for name in ("webhook_retry_queue", "webhook_dlq")}
    config = _get_alembic_config(url)
    await asyncio.to_thread(command.downgrade, config, "f6a7b8c9d0e1")
    await run_migrations(url)
    if target in ARCHIVES:
        await asyncio.to_thread(command.downgrade, config, "f6a7b8c9d0e1")
    return original


async def enforced_foreign_keys(connection):
    if connection.dialect.name == "sqlite":
        await connection.execute(text("PRAGMA foreign_keys = ON"))
        assert (await connection.execute(text("PRAGMA foreign_keys"))).scalar_one() == 1
    else:
        assert (await connection.execute(text("SHOW session_replication_role"))).scalar_one() == "origin"
    await connection.commit()


@scenario([params(target, style) for target in TARGETS for style in ("upper", "mixed")])
async def differently_cased_foreign_references_refuse_capture_or_ack_before_cascade(target, style):
    async with isolated_database_url() as url:
        original = await prepared_owned_sources(url, target)
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                with given("enforced incoming references using uppercase or mixed-case target identifiers"):
                    await enforced_foreign_keys(connection)
                    reference = reference_name(target, style)
                    if connection.dialect.name == "sqlite":
                        reference = f'"{reference}"'
                    if target == ARCHIVES[0]:
                        columns = f"archive_id TEXT REFERENCES {reference}(archive_id) ON DELETE CASCADE"
                        selected, predicate = "archive_id", "WHERE archive_id != '__contract_v1__'"
                    elif target in ARCHIVES:
                        columns = f"archive_id TEXT, target_id INTEGER, FOREIGN KEY(archive_id,target_id) REFERENCES {reference}(archive_id,id) ON DELETE CASCADE"
                        selected, predicate = "archive_id, id", ""
                    else:
                        columns = f"target_id INTEGER REFERENCES {reference}(id) ON DELETE CASCADE"
                        selected = "id"
                        predicate = "WHERE id = 7" if target == "webhook_retry_queue" else "WHERE id = 4"
                    await connection.execute(
                        text(f"CREATE TABLE external_case_owner (id INTEGER PRIMARY KEY, {columns})")
                    )
                    await connection.execute(
                        text(f"INSERT INTO external_case_owner SELECT 1, {selected} FROM {target} {predicate}")
                    )
                    await connection.commit()
                    before = await supplied_snapshot(url, connection)
                    await connection.rollback()

                with when("public Alembic would capture a source or acknowledge its durable archive"):
                    with catched(RuntimeError) as refused:
                        await supplied_migration(url, connection, "upgrade" if target in ARCHIVES else "downgrade")
                    after = await supplied_snapshot(url, connection)

                with then("refusal preserves the owner, raw schema/data, control/pending, revision and sequence state"):
                    assert refused.type is RuntimeError
                    assert "references" in str(refused.value)
                    assert after == before
                    assert len(after["persistent"]["external_case_owner"]["rows"]) == 1
                    if connection.dialect.name == "sqlite":
                        assert (await connection.execute(text("PRAGMA foreign_keys"))).scalar_one() == 1
        finally:
            await engine.dispose()

        with when("the physical connection is closed and only the test dependency is removed before healthy replay"):
            async with Database(url) as database, database.transaction() as session:
                await session.execute(text("DROP TABLE external_case_owner"))
            if target not in ARCHIVES:
                await asyncio.to_thread(command.downgrade, _get_alembic_config(url), "f6a7b8c9d0e1")
            await run_migrations(url)
            restored = {name: await raw_rows(url, name) for name in original}
            reopened = await snapshot(url)

        with then("all original rows return unchanged and only verified durable pending batches are acknowledged"):
            assert restored == original
            for name in ARCHIVES:
                assert all(row["archive_id"] == "__contract_v1__" for row in reopened[name]["rows"])


@scenario([params("webhook_retry_queue", "upper"), params(ARCHIVES[0], "mixed")])
async def distinct_unicode_sqlite_or_quoted_postgres_parent_is_not_a_canonical_target(target, style):
    async with isolated_database_url() as url:
        original = await prepared_owned_sources(url, target)
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                with given("an enforced FK to a separate Unicode SQLite or case-sensitive quoted PostgreSQL parent"):
                    await enforced_foreign_keys(connection)
                    parent = reference_name(target, style)
                    if connection.dialect.name == "sqlite":
                        parent = (
                            parent.replace("K", "\N{KELVIN SIGN}", 1)
                            if "K" in parent
                            else parent.replace("k", "\N{KELVIN SIGN}", 1)
                        )
                    quote = connection.dialect.identifier_preparer.quote
                    await connection.execute(
                        text(f"CREATE TABLE {quote(parent)} (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
                    )
                    await connection.execute(text(f"INSERT INTO {quote(parent)} VALUES (55, 'external-owned')"))
                    await connection.execute(
                        text(
                            f"CREATE TABLE external_case_owner (id INTEGER PRIMARY KEY, target_id INTEGER REFERENCES {quote(parent)}(id) ON DELETE CASCADE)"
                        )
                    )
                    await connection.execute(text("INSERT INTO external_case_owner VALUES (1, 55)"))
                    await connection.commit()
                    before = await supplied_snapshot(url, connection)
                    await connection.rollback()

                with when("the real migration operates only on canonical relation identities"):
                    if target not in ARCHIVES:
                        await supplied_migration(url, connection, "downgrade")
                    await supplied_migration(url, connection, "upgrade")
                    after = await supplied_snapshot(url, connection)

                with then("the distinct parent's actual data and FK remain intact without a false ownership refusal"):
                    assert after["persistent"][parent] == before["persistent"][parent]
                    assert after["persistent"]["external_case_owner"] == before["persistent"]["external_case_owner"]
                    assert after["persistent"][parent]["rows"] == [{"id": 55, "payload": "external-owned"}]
                    assert {name: after["persistent"][name]["rows"] for name in original} == original
        finally:
            await engine.dispose()
