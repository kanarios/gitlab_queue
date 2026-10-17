import asyncio

from alembic import command
from scenarios.contexts.database_backend import isolated_database_url
from sqlalchemy import text
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import _get_alembic_config, run_migrations

from ._archive_helpers import seed_dead, seed_retry, snapshot


@scenario([params("retry", False), params("retry", True), params("dlq", False), params("dlq", True)])
async def every_occupied_global_restore_id_fails_without_overwriting(table, identical):
    async with isolated_database_url() as url:
        with given("an archived source and an unproven live row occupying its table-global identity"):
            await run_migrations(url)
            if table == "retry":
                await seed_retry(url)
            else:
                await seed_dead(url, original="2000-01-01 00:00:00", moved=None)
            await asyncio.to_thread(command.downgrade, _get_alembic_config(url), "f6a7b8c9d0e1")
            if table == "retry":
                await seed_retry(
                    url, project_id=123 if identical else 456, created_at=None if identical else "2001-01-01 00:00:00"
                )
            else:
                await seed_dead(
                    url,
                    project_id=123 if identical else 456,
                    original="2000-01-01 00:00:00",
                    moved=None if identical else "2001-01-01 00:00:00",
                )
            before = await snapshot(url)

        with when("startup attempts restoration into an occupied identity, even with identical raw data"):
            with catched(RuntimeError) as refused:
                await run_migrations(url)
            after = await snapshot(url)

        with then("all archive/live data, schema and migration ownership remain untouched"):
            assert refused.type is RuntimeError
            assert "identity collision" in str(refused.value)
            assert after == before


@scenario(
    [
        params("format_version = 2"),
        params("owner = 'other-owner'"),
        params("source_schema = '{}'"),
        params("retry_count = retry_count + 1"),
        params("retry_digest = 'changed'"),
    ]
)
async def unsupported_or_corrupted_archive_manifest_fails_before_mutation(change):
    async with isolated_database_url() as url:
        with given("a pending archive whose durable contract was changed"):
            await run_migrations(url)
            await seed_retry(url)
            await asyncio.to_thread(command.downgrade, _get_alembic_config(url), "f6a7b8c9d0e1")
            async with Database(url) as database, database.transaction() as session:
                await session.execute(text(f"UPDATE gq_retry_rollback_manifest_v1 SET {change}"))
            before = await snapshot(url)

        with when("upgrade validates archive ownership/version/source/count/digest"):
            with catched(RuntimeError) as refused:
                await run_migrations(url)
            after = await snapshot(url)

        with then("invalid provenance is never adopted and every raw row remains recoverable"):
            assert refused.type is RuntimeError
            assert "Rollback archive" in str(refused.value)
            assert after == before


@scenario([params("payload"), params("missing_table"), params("extra_column")])
async def corrupted_archive_rows_or_shape_are_preserved_for_operator_recovery(kind):
    async with isolated_database_url() as url:
        with given("an archive with raw-row corruption or an unsupported physical shape"):
            await run_migrations(url)
            await seed_retry(url)
            await asyncio.to_thread(command.downgrade, _get_alembic_config(url), "f6a7b8c9d0e1")
            async with Database(url) as database, database.transaction() as session:
                statement = {
                    "payload": "UPDATE gq_retry_rollback_rows_v1 SET payload = 'changed bytes'",
                    "missing_table": "DROP TABLE gq_dlq_rollback_rows_v1",
                    "extra_column": "ALTER TABLE gq_retry_rollback_rows_v1 ADD COLUMN unsupported TEXT",
                }[kind]
                await session.execute(text(statement))
            before = await snapshot(url)

        with when("startup encounters this unverified archive"):
            with catched(RuntimeError) as refused:
                await run_migrations(url)
            after = await snapshot(url)

        with then("it neither repairs nor acknowledges questionable storage"):
            assert refused.type is RuntimeError
            assert "Rollback archive" in str(refused.value)
            assert after == before


@scenario([params("foreign_reference"), params("source_column"), params("unowned_archive")])
async def unsupported_source_schema_or_external_references_stop_archive_deletion(kind):
    async with isolated_database_url() as url:
        with given("a source whose external ownership or shape cannot be archived safely"):
            await run_migrations(url)
            await seed_retry(url)
            async with Database(url) as database, database.transaction() as session:
                statement = {
                    "foreign_reference": "CREATE TABLE external_retry_reference (retry_id INTEGER REFERENCES webhook_retry_queue(id) ON DELETE CASCADE)",
                    "source_column": "ALTER TABLE webhook_retry_queue ADD COLUMN unsupported TEXT",
                    "unowned_archive": "CREATE TABLE gq_retry_rollback_manifest_v1 (unrelated TEXT)",
                }[kind]
                await session.execute(text(statement))
                if kind == "foreign_reference":
                    await session.execute(text("INSERT INTO external_retry_reference (retry_id) VALUES (7)"))
            before = await snapshot(url)

        with when("raw Alembic attempts to downgrade that source"):
            with catched(RuntimeError) as refused:
                await asyncio.to_thread(command.downgrade, _get_alembic_config(url), "f6a7b8c9d0e1")
            after = await snapshot(url)

        with then("no cascading deletion, ignored column or unowned archive adoption occurs"):
            assert refused.type is RuntimeError
            assert "Rollback archive" in str(refused.value)
            assert after == before
