from datetime import UTC, datetime, timedelta, timezone

from vedro import given, scenario, then, when

from gitlab_queue.db.models import WebhookDLQModel
from gitlab_queue.webhooks.retry_manager import WebhookRetryManager

from ._helpers import migrated_storage
from .retry_backoff_exact_boundaries import Clock


@scenario()
async def exact_retention_boundary_preserves_valid_mixed_timestamp_formats():
    async with migrated_storage() as database:
        with given("DLQ timestamps one microsecond before, on and after the retention boundary"):
            clock = Clock(datetime(2026, 10, 17, 12, 0, 0, 123456, tzinfo=UTC))
            cutoff = clock.instant - timedelta(days=30)
            values = [
                (cutoff - timedelta(microseconds=1)).astimezone(timezone(timedelta(hours=5))).isoformat(),
                cutoff.strftime("%Y-%m-%d %H:%M:%S.%f"),
                (cutoff + timedelta(microseconds=1)).isoformat().replace("+00:00", "Z"),
            ]
            async with database.transaction() as session:
                session.add_all(
                    [
                        WebhookDLQModel(
                            project_id=123,
                            event_type="merge_request",
                            payload="{}",
                            attempt_count=1,
                            last_error="failure",
                            original_created_at=value,
                            moved_to_dlq_at=value,
                        )
                        for value in values
                    ]
                )
            manager = WebhookRetryManager(database, clock=clock)

        with when("thirty-day cleanup applies a strict older-than comparison"):
            deleted = await manager.cleanup_old_dlq_entries(days=30)
            remaining = await manager.get_dlq_entries(project_id=123)
            stats = await manager.get_dlq_stats(project_id=123)

        with then("only the earlier instant expires, regardless of text representation"):
            assert deleted == 1
            assert len(remaining) == 2
            assert remaining[0].moved_to_dlq_at == cutoff + timedelta(microseconds=1)
            assert remaining[1].moved_to_dlq_at == cutoff
            assert stats.oldest_entry == cutoff
