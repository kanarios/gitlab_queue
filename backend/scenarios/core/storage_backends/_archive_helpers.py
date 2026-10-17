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


async def snapshot(url):
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
            }
        if database.engine.dialect.name == "sqlite":
            result["sqlite_sequence"] = list(
                (await connection.execute(text("SELECT name, seq FROM sqlite_sequence ORDER BY name"))).all()
            )
        return result


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
