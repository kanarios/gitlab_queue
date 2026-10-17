from scenarios.contexts.database_backend import isolated_database_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from vedro import catched, given, params, scenario, then, when

from ._archive_helpers import ARCHIVES, seed_dead, supplied_migration, supplied_snapshot
from .archive_mutation_safety import TARGETS, prepared_target


@scenario([params(target) for target in TARGETS])
async def supplied_connection_trigger_refuses_before_deleting_another_project(target):
    async with isolated_database_url() as url:
        await prepared_target(url, target)
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                with given("a SQLite TEMP trigger on the supplied physical connection, or a PostgreSQL user trigger"):
                    if connection.dialect.name == "sqlite":
                        await connection.execute(
                            text(
                                f"CREATE TEMP TRIGGER supplied_effect AFTER DELETE ON main.{target} "
                                "BEGIN DELETE FROM webhook_retry_queue WHERE id = 8; END"
                            )
                        )
                    else:
                        await connection.execute(
                            text(
                                "CREATE FUNCTION supplied_effect() RETURNS trigger LANGUAGE plpgsql AS $$ "
                                "BEGIN DELETE FROM webhook_retry_queue WHERE id = 8; RETURN OLD; END $$"
                            )
                        )
                        await connection.execute(
                            text(
                                f"CREATE TRIGGER supplied_effect AFTER DELETE ON {target} FOR EACH ROW EXECUTE FUNCTION supplied_effect()"
                            )
                        )
                    await connection.commit()
                    before = await supplied_snapshot(url, connection)
                    await connection.rollback()

                with when("public Alembic uses that exact connection for capture or acknowledgment"):
                    with catched(RuntimeError) as refused:
                        await supplied_migration(url, connection, "upgrade" if target in ARCHIVES else "downgrade")
                    after = await supplied_snapshot(url, connection)

                with then("preflight preserves durable and temporary definitions, data, version and sequences"):
                    assert refused.type is RuntimeError
                    assert "trigger" in str(refused.value)
                    assert after == before
                    assert [
                        row["id"]
                        for row in after["persistent"]["webhook_retry_queue"]["rows"]
                        if row["project_id"] == 456
                    ] == [8]
        finally:
            await engine.dispose()


@scenario([params(target) for target in TARGETS])
async def supplied_connection_rewrite_rule_or_temp_trigger_cannot_delete_compatible_data(target):
    async with isolated_database_url() as url:
        await prepared_target(url, target)
        await seed_dead(url, entry_id=8, project_id=456, original="2000-01-01", moved="2000-01-01")
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                with given("a PostgreSQL delete rewrite rule, or a SQLite TEMP trigger, affecting another table"):
                    victim = "webhook_retry_queue" if target == "webhook_dlq" else "webhook_dlq"
                    if connection.dialect.name == "postgresql":
                        await connection.execute(
                            text(
                                f"CREATE RULE supplied_rewrite AS ON DELETE TO {target} DO ALSO DELETE FROM {victim} WHERE id = 8"
                            )
                        )
                    else:
                        await connection.execute(
                            text(
                                f"CREATE TEMP TRIGGER supplied_effect AFTER DELETE ON main.{target} BEGIN DELETE FROM {victim} WHERE id = 8; END"
                            )
                        )
                    await connection.commit()
                    before = await supplied_snapshot(url, connection)
                    await connection.rollback()

                with when("capture or ACK would execute behavior outside the frozen storage contract"):
                    with catched(RuntimeError) as refused:
                        await supplied_migration(url, connection, "upgrade" if target in ARCHIVES else "downgrade")
                    after = await supplied_snapshot(url, connection)

                with then("preflight retains rule definitions, all raw data and exact sequence and revision state"):
                    assert refused.type is RuntimeError
                    assert ("rewrite rule" if connection.dialect.name == "postgresql" else "trigger") in str(
                        refused.value
                    )
                    assert after == before
                    for table in ("webhook_retry_queue", "webhook_dlq"):
                        assert any(
                            row["id"] == 8 and row["project_id"] == 456 for row in after["persistent"][table]["rows"]
                        )
        finally:
            await engine.dispose()


@scenario([params("parent"), params("child")])
async def inherited_or_connection_local_dependencies_cannot_expand_archive_mutations(orientation):
    async with isolated_database_url() as url:
        await prepared_target(url, "webhook_retry_queue")
        await seed_dead(url, entry_id=8, project_id=456, original="2000-01-01", moved="2000-01-01")
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                with given(
                    "a PostgreSQL inheritance edge, or a SQLite TEMP-trigger dependency, outside the five targets"
                ):
                    if connection.dialect.name == "postgresql":
                        if orientation == "parent":
                            await connection.execute(
                                text("CREATE TABLE external_retry_child () INHERITS (webhook_retry_queue)")
                            )
                            await connection.execute(
                                text(
                                    "INSERT INTO external_retry_child SELECT * FROM ONLY webhook_retry_queue WHERE id = 7"
                                )
                            )
                            await connection.execute(text("DELETE FROM ONLY webhook_retry_queue WHERE id = 7"))
                            await connection.execute(
                                text(
                                    "CREATE FUNCTION inherited_effect() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN DELETE FROM webhook_dlq WHERE id = 8; RETURN OLD; END $$"
                                )
                            )
                            await connection.execute(
                                text(
                                    "CREATE TRIGGER inherited_effect AFTER DELETE ON external_retry_child FOR EACH ROW EXECUTE FUNCTION inherited_effect()"
                                )
                            )
                        else:
                            await connection.execute(
                                text("CREATE TABLE external_retry_parent (LIKE webhook_retry_queue)")
                            )
                            await connection.execute(
                                text("ALTER TABLE webhook_retry_queue INHERIT external_retry_parent")
                            )
                    else:
                        await connection.execute(
                            text("CREATE TABLE external_retry_child AS SELECT * FROM webhook_retry_queue WHERE id = 7")
                        )
                        await connection.execute(
                            text(
                                "CREATE TEMP TRIGGER inherited_effect AFTER DELETE ON main.webhook_retry_queue BEGIN DELETE FROM external_retry_child WHERE id = 7; DELETE FROM webhook_dlq WHERE id = 8; END"
                            )
                        )
                    await connection.commit()
                    before = await supplied_snapshot(url, connection)
                    await connection.rollback()

                with when("public downgrade would include child-owned rows or execute a connection-local side effect"):
                    with catched(RuntimeError) as refused:
                        await supplied_migration(url, connection, "downgrade")
                    after = await supplied_snapshot(url, connection)

                with then("the dependency, physical row ownership, foreign-project data and exact sequences survive"):
                    assert refused.type is RuntimeError
                    assert ("inheritance" if connection.dialect.name == "postgresql" else "trigger") in str(
                        refused.value
                    )
                    assert after == before
                    assert any(
                        row["id"] == 8 and row["project_id"] == 456
                        for row in after["persistent"]["webhook_dlq"]["rows"]
                    )
        finally:
            await engine.dispose()
