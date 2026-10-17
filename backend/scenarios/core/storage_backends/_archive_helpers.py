import asyncio
import os
import sys
import time
from pathlib import Path

from alembic import command
from sqlalchemy import event, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import _get_alembic_config

ARCHIVES = ("gq_retry_rollback_manifest_v1", "gq_retry_rollback_rows_v1", "gq_dlq_rollback_rows_v1")
PAYLOAD = ' {"duplicate": 1, "duplicate": 2, "unicode": "ёж", "nested": [null, true]} '


async def seed_retry(url, entry_id=7, project_id=123, created_at=None, due="2000-01-01 00:00:00"):
    async with Database(url) as database, database.transaction() as session:
        await session.execute(
            text(
                "INSERT INTO webhook_retry_queue (id, project_id, event_type, payload, attempt_count, max_attempts, next_attempt_at, last_error, created_at) VALUES (:id, :project, 'merge_request', :payload, 4, 7, :due, 'exact error', :created)"
            ),
            {"id": entry_id, "project": project_id, "payload": PAYLOAD, "due": due, "created": created_at},
        )


async def seed_dead(url, entry_id=4, project_id=123, original=None, moved="2026-10-16T23:15:00.123456+05:00"):
    async with Database(url) as database, database.transaction() as session:
        await session.execute(
            text(
                "INSERT INTO webhook_dlq (id, project_id, event_type, payload, attempt_count, last_error, original_created_at, moved_to_dlq_at) VALUES (:id, :project, 'merge_request', :payload, 7, 'exact failure', :original, :moved)"
            ),
            {"id": entry_id, "project": project_id, "payload": PAYLOAD, "original": original, "moved": moved},
        )


async def snapshot(url, *, include_sequences=False):
    async with Database(url) as database, database.engine.connect() as connection:
        tables = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
        result = {}
        for table in tables:
            columns = await connection.run_sync(lambda sync, name=table: inspect(sync).get_columns(name))
            result[table] = {
                "columns": [
                    (column["name"], str(column["type"]), column["nullable"], str(column["default"]))
                    for column in columns
                ],
                "rows": sorted(
                    [dict(row) for row in (await connection.execute(text(f"SELECT * FROM {table}"))).mappings()],
                    key=repr,
                ),
                "constraints": await connection.run_sync(
                    lambda sync, name=table: {
                        "primary": inspect(sync).get_pk_constraint(name),
                        "foreign": inspect(sync).get_foreign_keys(name),
                        "unique": inspect(sync).get_unique_constraints(name),
                        "check": inspect(sync).get_check_constraints(name),
                        "indexes": inspect(sync).get_indexes(name),
                    }
                ),
            }
        if database.engine.dialect.name == "sqlite":
            result["triggers"] = list(
                (
                    await connection.execute(
                        text("SELECT name, sql FROM sqlite_master WHERE type = 'trigger' ORDER BY name")
                    )
                ).all()
            )
            result["sqlite_sequence"] = list(
                (await connection.execute(text("SELECT name, seq FROM sqlite_sequence ORDER BY name"))).all()
            )
        else:
            result["inheritance"] = list(
                (
                    await connection.execute(
                        text(
                            "SELECT pn.nspname, p.relname, cn.nspname, c.relname FROM pg_inherits i "
                            "JOIN pg_class p ON p.oid = i.inhparent JOIN pg_namespace pn ON pn.oid = p.relnamespace "
                            "JOIN pg_class c ON c.oid = i.inhrelid JOIN pg_namespace cn ON cn.oid = c.relnamespace "
                            "WHERE pn.nspname = current_schema() OR cn.nspname = current_schema() "
                            "ORDER BY pn.nspname, p.relname, cn.nspname, c.relname"
                        )
                    )
                ).all()
            )
            result["rules"] = list(
                (
                    await connection.execute(
                        text(
                            "SELECT r.rulename, pg_get_ruledef(r.oid) FROM pg_rewrite r "
                            "JOIN pg_class c ON c.oid = r.ev_class JOIN pg_namespace n ON n.oid = c.relnamespace "
                            "WHERE n.nspname = current_schema() ORDER BY r.rulename"
                        )
                    )
                ).all()
            )
            result["triggers"] = list(
                (
                    await connection.execute(
                        text(
                            "SELECT t.tgname, pg_get_triggerdef(t.oid), pg_get_functiondef(t.tgfoid) "
                            "FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                            "JOIN pg_namespace n ON n.oid = c.relnamespace "
                            "WHERE n.nspname = current_schema() AND NOT t.tgisinternal ORDER BY t.tgname"
                        )
                    )
                ).all()
            )
            if include_sequences:
                names = (
                    await connection.execute(
                        text(
                            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                            "WHERE c.relkind = 'S' AND n.nspname = current_schema() ORDER BY c.relname"
                        )
                    )
                ).scalars()
                result["postgres_sequences"] = {
                    name: tuple((await connection.execute(text(f'SELECT last_value, is_called FROM "{name}"'))).one())
                    for name in names
                }
        return result


async def supplied_snapshot(url, connection):
    """Record durable storage separately from same-connection TEMP objects."""
    result = {"persistent": await snapshot(url, include_sequences=True)}
    if connection.dialect.name == "sqlite":
        objects = (
            await connection.execute(text("SELECT type, name, sql FROM sqlite_temp_master ORDER BY type, name"))
        ).all()
        schema = "temp"
    else:
        schema = (
            await connection.execute(text("SELECT nspname FROM pg_namespace WHERE oid = pg_my_temp_schema()"))
        ).scalar()
        objects = (
            await connection.execute(
                text(
                    "SELECT c.relkind::text, c.relname, CASE WHEN c.relkind = 'v' THEN pg_get_viewdef(c.oid) END "
                    "FROM pg_class c WHERE c.relnamespace = pg_my_temp_schema() AND c.relkind IN ('r', 'v') "
                    "ORDER BY c.relkind, c.relname"
                )
            )
        ).all()
    result["temporary_definitions"] = list(objects)
    quote = connection.dialect.identifier_preparer.quote
    result["temporary_rows"] = {
        name: sorted(
            [
                dict(row)
                for row in (await connection.execute(text(f"SELECT * FROM {quote(schema)}.{quote(name)}"))).mappings()
            ],
            key=repr,
        )
        for kind, name, _ in objects
        if kind in ("table", "view", "r", "v")
    }
    return result


async def supplied_migration(url, connection, direction):
    def migrate(sync):
        config = _get_alembic_config(url)
        config.attributes["connection"] = sync
        getattr(command, direction)(config, "f6a7b8c9d0e1" if direction == "downgrade" else "head")

    await connection.run_sync(migrate)


async def observed_migration(url, direction, stage, mode="raise", marker=None, release=None):
    engine = create_async_engine(url)
    hit = False
    try:
        async with engine.connect() as connection:

            def migrate(sync):
                nonlocal hit
                schema_sql = (
                    "DROP TABLE webhook_retry_queue"
                    if sync.dialect.name == "sqlite"
                    else "ALTER TABLE webhook_retry_queue"
                )
                target = {
                    "copy": "INSERT INTO gq_retry_rollback_rows_v1",
                    "delete": "DELETE FROM webhook_retry_queue",
                    "schema": schema_sql,
                    "version": "UPDATE alembic_version",
                    "restore": "INSERT INTO webhook_retry_queue",
                    "ack": "DELETE FROM gq_retry_rollback_rows_v1",
                }[stage].upper()

                def observe(_connection, _cursor, statement, _parameters, _context, _many):
                    nonlocal hit
                    if hit or not " ".join(statement.split()).upper().startswith(target):
                        return
                    hit = True
                    if marker:
                        Path(marker).write_text("reached")
                    if mode == "crash":
                        os._exit(23)
                    if mode == "hold":
                        deadline = time.monotonic() + 10
                        while not Path(release).exists():
                            if time.monotonic() > deadline:
                                raise RuntimeError("migration barrier timed out")
                            time.sleep(0.01)
                        return
                    raise RuntimeError("injected migration interruption")

                event.listen(sync, "after_cursor_execute", observe)
                config = _get_alembic_config(url)
                config.attributes["connection"] = sync
                try:
                    getattr(command, direction)(config, "f6a7b8c9d0e1" if direction == "downgrade" else "head")
                finally:
                    event.remove(sync, "after_cursor_execute", observe)

            await connection.run_sync(migrate)
    finally:
        await engine.dispose()
    if not hit:
        raise RuntimeError("migration observer target was not reached")


async def child_migration(url, direction, stage, mode, marker, release):
    code = "import asyncio,os; from scenarios.core.storage_backends._archive_helpers import observed_migration; asyncio.run(observed_migration(os.environ['GQ_CHILD_URL'],os.environ['GQ_DIRECTION'],os.environ['GQ_STAGE'],os.environ['GQ_MODE'],os.environ['GQ_MARKER'],os.environ['GQ_RELEASE']))"
    env = dict(
        os.environ,
        GQ_CHILD_URL=url,
        GQ_DIRECTION=direction,
        GQ_STAGE=stage,
        GQ_MODE=mode,
        GQ_MARKER=str(marker),
        GQ_RELEASE=str(release),
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", code, env=env, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
    )
    return process


async def wait_file(path):
    async def wait():
        while not path.exists():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait(), timeout=10)
