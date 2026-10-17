import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from alembic import command
from scenarios.contexts.database_backend import isolated_database_url
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.db.migrations import _get_alembic_config, run_migrations

from ._archive_helpers import child_migration, observed_migration, seed_retry, snapshot
from .automatic_downgrade_archive import raw_rows


@scenario(
    [
        params("downgrade", "copy"),
        params("downgrade", "delete"),
        params("downgrade", "schema"),
        params("downgrade", "version"),
        params("upgrade", "restore"),
        params("upgrade", "ack"),
        params("upgrade", "version"),
    ]
)
async def archive_interruption_rolls_back_rows_schema_and_version(direction, stage):
    async with isolated_database_url() as url:
        with given("a real migrated source at the archive or restoration boundary"):
            await run_migrations(url)
            await seed_retry(url)
            original = await raw_rows(url, "webhook_retry_queue")
            if direction == "upgrade":
                await asyncio.to_thread(command.downgrade, _get_alembic_config(url), "f6a7b8c9d0e1")
            before = await snapshot(url)

        with when("a real SQL observer interrupts after an archive, DDL, restore, ACK or version statement"):
            with catched(RuntimeError) as interrupted:
                await observed_migration(url, direction, stage)
            after = await snapshot(url)
            if direction == "downgrade":
                await asyncio.to_thread(command.downgrade, _get_alembic_config(url), "f6a7b8c9d0e1")
            await run_migrations(url)
            restored = await raw_rows(url, "webhook_retry_queue")

        with then(
            "the physical transaction preserves the complete pre-boundary state and healthy replay restores once"
        ):
            assert interrupted.type is RuntimeError
            assert str(interrupted.value) == "injected migration interruption"
            assert after == before
            assert restored == original


@scenario([params("downgrade", "schema"), params("upgrade", "ack")])
async def process_exit_before_migration_commit_recovers_after_reopen(direction, stage):
    async with isolated_database_url() as url:
        with given("an archived or active retry whose migration process will exit after executing SQL"):
            await run_migrations(url)
            await seed_retry(url)
            original = await raw_rows(url, "webhook_retry_queue")
            if direction == "upgrade":
                await asyncio.to_thread(command.downgrade, _get_alembic_config(url), "f6a7b8c9d0e1")
            before = await snapshot(url)

        with when("the child dies without rollback handlers after batch DDL or archive ACK"):
            with TemporaryDirectory() as directory:
                marker = Path(directory) / "executed"
                child = await child_migration(url, direction, stage, "crash", marker, Path(directory) / "unused")
                returncode = await asyncio.wait_for(child.wait(), timeout=15)
                assert marker.exists()
            after = await snapshot(url)
            if direction == "downgrade":
                await asyncio.to_thread(command.downgrade, _get_alembic_config(url), "f6a7b8c9d0e1")
            await run_migrations(url)
            restored = await raw_rows(url, "webhook_retry_queue")

        with then("database recovery restores the transaction boundary and startup resumes the exact event"):
            assert returncode == 23
            assert after == before
            assert restored == original
