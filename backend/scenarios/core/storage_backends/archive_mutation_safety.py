import asyncio

from alembic import command
from scenarios.contexts.database_backend import isolated_database_url
from sqlalchemy import text
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import _get_alembic_config, run_migrations

from ._archive_helpers import ARCHIVES, seed_dead, seed_retry, snapshot

TARGETS = ("webhook_retry_queue", "webhook_dlq", *ARCHIVES)


async def prepared_target(url, target):
    await run_migrations(url)
    await seed_retry(url)
    await seed_retry(url, entry_id=8, project_id=456, created_at="2000-01-01 00:00:00")
    await seed_dead(url)
    if target in ARCHIVES:
        await asyncio.to_thread(command.downgrade, _get_alembic_config(url), "f6a7b8c9d0e1")


async def migrate_target(url, target):
    if target in ARCHIVES:
        await run_migrations(url)
    else:
        await asyncio.to_thread(command.downgrade, _get_alembic_config(url), "f6a7b8c9d0e1")


@scenario([params(target) for target in TARGETS])
async def unsupported_delete_trigger_on_every_mutation_target_refuses_before_side_effects(target):
    async with isolated_database_url() as url:
        with given("a user trigger that deletes an unrelated compatible row in another project"):
            await prepared_target(url, target)
            async with Database(url) as database, database.transaction() as session:
                if database.engine.dialect.name == "sqlite":
                    await session.execute(
                        text(
                            f"CREATE TRIGGER unsupported_archive_trigger AFTER DELETE ON {target} "
                            "BEGIN DELETE FROM webhook_retry_queue WHERE id = 8; END"
                        )
                    )
                else:
                    await session.execute(
                        text(
                            "CREATE FUNCTION unsupported_archive_effect() RETURNS trigger LANGUAGE plpgsql AS $$ "
                            "BEGIN DELETE FROM webhook_retry_queue WHERE id = 8; RETURN OLD; END $$"
                        )
                    )
                    await session.execute(
                        text(
                            f"CREATE TRIGGER unsupported_archive_trigger AFTER DELETE ON {target} "
                            "FOR EACH ROW EXECUTE FUNCTION unsupported_archive_effect()"
                        )
                    )
            before = await snapshot(url, include_sequences=True)

        with when("the public migrator would delete source rows or acknowledge archive rows"):
            with catched(RuntimeError) as refused:
                await migrate_target(url, target)
            after = await snapshot(url, include_sequences=True)

        with then("preflight refuses the trigger without any data, schema, sequence or trigger-definition change"):
            assert refused.type is RuntimeError
            assert "trigger" in str(refused.value)
            assert after == before
            assert [row["id"] for row in after["webhook_retry_queue"]["rows"] if row["project_id"] == 456] == [8]


@scenario([params(target) for target in TARGETS])
async def incoming_cascade_reference_to_every_mutation_target_refuses_before_external_deletion(target):
    async with isolated_database_url() as url:
        with given("an external owner referencing a live or pending archived row with ON DELETE CASCADE"):
            await prepared_target(url, target)
            async with Database(url) as database, database.transaction() as session:
                if target == ARCHIVES[0]:
                    columns = "archive_id TEXT REFERENCES gq_retry_rollback_manifest_v1(archive_id) ON DELETE CASCADE"
                    selected = "archive_id"
                    predicate = "WHERE archive_id != '__contract_v1__'"
                elif target in ARCHIVES:
                    columns = (
                        f"archive_id TEXT, target_id INTEGER, FOREIGN KEY(archive_id, target_id) "
                        f"REFERENCES {target}(archive_id, id) ON DELETE CASCADE"
                    )
                    selected = "archive_id, id"
                    predicate = ""
                else:
                    columns = f"target_id INTEGER REFERENCES {target}(id) ON DELETE CASCADE"
                    selected = "id"
                    predicate = "WHERE id = 7" if target == "webhook_retry_queue" else "WHERE id = 4"
                await session.execute(text(f"CREATE TABLE external_archive_owner (id INTEGER PRIMARY KEY, {columns})"))
                await session.execute(
                    text(f"INSERT INTO external_archive_owner SELECT 1, {selected} FROM {target} {predicate}")
                )
            before = await snapshot(url, include_sequences=True)

        with when("the public migrator checks ownership of all five tables before mutation"):
            with catched(RuntimeError) as refused:
                await migrate_target(url, target)
            after = await snapshot(url, include_sequences=True)

        with then("the external row and its constraint survive without touching raw data, revision or sequence state"):
            assert refused.type is RuntimeError
            assert "references" in str(refused.value)
            assert after == before
            assert len(after["external_archive_owner"]["rows"]) == 1
