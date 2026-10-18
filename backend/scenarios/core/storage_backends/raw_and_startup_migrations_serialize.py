import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from scenarios.contexts.database_backend import isolated_database_url
from vedro import given, scenario, then, when

from gitlab_queue.db.migrations import get_current_revision, run_migrations

from ._archive_helpers import child_migration, seed_retry, wait_file
from .automatic_downgrade_archive import raw_rows


@scenario()
async def already_at_head_startup_waits_for_raw_downgrade_then_restores():
    async with isolated_database_url() as url:
        with TemporaryDirectory() as directory:
            marker, release = Path(directory) / "held", Path(directory) / "release"
            with given("raw Alembic holds an uncommitted a7 downgrade after copying an unknown retry"):
                await run_migrations(url)
                await seed_retry(url)
                original = await raw_rows(url, "webhook_retry_queue")
                raw = await child_migration(url, "downgrade", "copy", "hold", marker, release)
                await wait_file(marker)

            with when("already-at-head startup overlaps that raw migration"):
                startup = asyncio.create_task(run_migrations(url))
                try:
                    # The raw SQL barrier remains held throughout this bounded
                    # observation; startup must not ACK its old committed head.
                    completed, _ = await asyncio.wait({startup}, timeout=1)
                    premature = startup.result() if completed else None
                finally:
                    release.write_text("continue")
                assert await asyncio.wait_for(raw.wait(), timeout=10) == 0
                upgraded = await asyncio.wait_for(startup, timeout=10)
                revision = await get_current_revision(url)
                restored = await raw_rows(url, "webhook_retry_queue")

            with then("one common gate protects classification through DDL without self-deadlock"):
                assert premature is None
                assert upgraded is True
                assert revision == "b8c9d0e1f2a3"
                assert restored == original
