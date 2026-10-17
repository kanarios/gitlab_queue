from datetime import UTC, datetime, timedelta

from scenarios.contexts.sqlite_client import initialized_test_database
from vedro import given, scenario, then, when

from ._helpers import create_test_payload, create_test_retry_manager


@scenario()
async def cleanup_old_dlq_entries_removes_expired():
    async with initialized_test_database() as database:
        with given("two entries moved to DLQ sixty days ago through the real manager"):
            old = datetime.now(UTC) - timedelta(days=60)
            manager = create_test_retry_manager(database, max_attempts=1, base_delay_seconds=0, clock=lambda: old)
            await manager.ensure_schema()
            for _ in range(2):
                retry_id = await manager.add_to_retry_queue("merge_request", create_test_payload(), "old")
                await manager.mark_retry_failed(retry_id, "final")
            current = create_test_retry_manager(database, max_attempts=1, base_delay_seconds=0)

        with when("the current manager applies thirty-day retention"):
            deleted = await current.cleanup_old_dlq_entries(days=30)

        with then("old entries are removed while a newly failed event is retained"):
            assert deleted == 2
            assert await current.get_dlq_entries() == []
            new_id = await current.add_to_retry_queue("merge_request", create_test_payload(), "new")
            await current.mark_retry_failed(new_id, "final")
            assert await current.cleanup_old_dlq_entries(days=99999) == 0
            assert len(await current.get_dlq_entries()) == 1
