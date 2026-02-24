"""Helper functions for DLQ API tests."""

from __future__ import annotations

from datetime import UTC, datetime

from gitlab_queue.models.retry import DLQItem, DLQStats


def create_test_dlq_item(
    entry_id: int = 1,
    event_type: str = "merge_request",
) -> DLQItem:
    """Create a test DLQ item.

    Args:
        entry_id: DLQ item database ID.
        event_type: Type of webhook event.

    Returns:
        DLQItem with test data.
    """
    return DLQItem(
        id=entry_id,
        event_type=event_type,
        payload={"object_kind": event_type, "test": True},
        attempt_count=3,
        last_error="Final error",
        original_created_at=datetime.now(UTC),
        moved_to_dlq_at=datetime.now(UTC),
    )


def create_test_dlq_stats(
    total: int = 0,
    by_event_type: dict[str, int] | None = None,
) -> DLQStats:
    """Create test DLQ statistics.

    Args:
        total: Total count of DLQ items.
        by_event_type: Optional breakdown by event type.

    Returns:
        DLQStats with test data.
    """
    return DLQStats(
        total_count=total,
        by_event_type=by_event_type or {},
        oldest_entry=None,
    )
