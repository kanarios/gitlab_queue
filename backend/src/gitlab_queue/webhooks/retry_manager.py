"""Webhook Retry Manager for GitLab Merge Queue Bot.

Manages the retry queue and Dead Letter Queue (DLQ) for failed webhook events.
Provides exponential backoff retry logic and DLQ management.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from gitlab_queue.models.retry import DLQItem, DLQStats, RetryQueueItem
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy import RowMapping

    from gitlab_queue.db.database import Database

log = get_logger(__name__)


# =============================================================================
# SQL Statements
# =============================================================================

_CREATE_RETRY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS webhook_retry_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    attempt_count INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    next_attempt_at TEXT NOT NULL,
    last_error TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_DLQ_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS webhook_dlq (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    attempt_count INTEGER NOT NULL,
    last_error TEXT NOT NULL,
    original_created_at TEXT NOT NULL,
    moved_to_dlq_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_RETRY_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_retry_next_attempt ON webhook_retry_queue(next_attempt_at)",
    "CREATE INDEX IF NOT EXISTS idx_retry_event_type ON webhook_retry_queue(event_type)",
]

_CREATE_DLQ_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_dlq_moved_at ON webhook_dlq(moved_to_dlq_at)",
    "CREATE INDEX IF NOT EXISTS idx_dlq_event_type ON webhook_dlq(event_type)",
]

_INSERT_RETRY_SQL = """
INSERT INTO webhook_retry_queue (
    event_type, payload, attempt_count, max_attempts, next_attempt_at, last_error, created_at
)
VALUES (
    :event_type, :payload, :attempt_count, :max_attempts, :next_attempt_at, :last_error, :created_at
)
"""

_SELECT_READY_FOR_RETRY_SQL = """
SELECT * FROM webhook_retry_queue
WHERE next_attempt_at <= :now
ORDER BY next_attempt_at ASC
LIMIT :limit
"""

_SELECT_RETRY_BY_ID_SQL = """
SELECT * FROM webhook_retry_queue WHERE id = :id
"""

_DELETE_RETRY_BY_ID_SQL = """
DELETE FROM webhook_retry_queue WHERE id = :id
"""

_UPDATE_RETRY_ATTEMPT_SQL = """
UPDATE webhook_retry_queue
SET attempt_count = :attempt_count,
    next_attempt_at = :next_attempt_at,
    last_error = :last_error
WHERE id = :id
"""

_INSERT_DLQ_SQL = """
INSERT INTO webhook_dlq (
    event_type, payload, attempt_count, last_error, original_created_at
)
VALUES (
    :event_type, :payload, :attempt_count, :last_error, :original_created_at
)
"""

_SELECT_DLQ_ALL_SQL = """
SELECT * FROM webhook_dlq
ORDER BY moved_to_dlq_at DESC
LIMIT :limit OFFSET :offset
"""

_SELECT_DLQ_BY_TYPE_SQL = """
SELECT * FROM webhook_dlq
WHERE event_type = :event_type
ORDER BY moved_to_dlq_at DESC
LIMIT :limit OFFSET :offset
"""

_SELECT_DLQ_BY_ID_SQL = """
SELECT * FROM webhook_dlq WHERE id = :id
"""

_DELETE_DLQ_BY_ID_SQL = """
DELETE FROM webhook_dlq WHERE id = :id
"""

_SELECT_DLQ_STATS_SQL = """
SELECT
    COUNT(*) as total_count,
    MIN(moved_to_dlq_at) as oldest_entry
FROM webhook_dlq
"""

_SELECT_DLQ_BY_TYPE_COUNT_SQL = """
SELECT event_type, COUNT(*) as count
FROM webhook_dlq
GROUP BY event_type
"""

_CLEANUP_OLD_DLQ_SQL = """
DELETE FROM webhook_dlq
WHERE moved_to_dlq_at < datetime('now', :days_param)
"""


# =============================================================================
# Custom Exceptions
# =============================================================================


class RetryQueueError(Exception):
    """Base exception for retry queue operations."""


class RetryItemNotFoundError(RetryQueueError):
    """Raised when a retry queue item is not found."""

    def __init__(self, item_id: int) -> None:
        self.item_id = item_id
        super().__init__(f"Retry queue item not found: {item_id}")


class DLQItemNotFoundError(RetryQueueError):
    """Raised when a DLQ item is not found."""

    def __init__(self, item_id: int) -> None:
        self.item_id = item_id
        super().__init__(f"DLQ item not found: {item_id}")


# =============================================================================
# Retry Manager
# =============================================================================


@dataclass
class WebhookRetryManager:
    """Manages retry queue and DLQ for failed webhook events.

    Provides exponential backoff retry logic with configurable parameters.
    Events that exceed max_attempts are moved to the DLQ for investigation.

    Attributes:
        db: Database instance for SQLite operations.
        max_attempts: Maximum retry attempts before moving to DLQ (default: 3).
        base_delay_seconds: Base delay for exponential backoff (default: 30).
        max_delay_seconds: Maximum delay cap for backoff (default: 300).

    Example:
        >>> manager = WebhookRetryManager(db=database)
        >>> await manager.ensure_schema()
        >>> retry_id = await manager.add_to_retry_queue(
        ...     event_type="merge_request",
        ...     payload={"object_kind": "merge_request", ...},
        ...     error="Connection timeout"
        ... )
    """

    db: Database
    max_attempts: int = 3
    base_delay_seconds: int = 30
    max_delay_seconds: int = 300

    async def ensure_schema(self) -> None:
        """Create retry queue and DLQ tables if they don't exist.

        Safe to call multiple times - uses CREATE IF NOT EXISTS.
        """
        log.debug("Ensuring retry queue schema exists")

        async with self.db.transaction() as session:
            await session.execute(text(_CREATE_RETRY_TABLE_SQL))
            await session.execute(text(_CREATE_DLQ_TABLE_SQL))
            for index_sql in _CREATE_RETRY_INDEXES_SQL:
                await session.execute(text(index_sql))
            for index_sql in _CREATE_DLQ_INDEXES_SQL:
                await session.execute(text(index_sql))

        log.info("Retry queue schema ensured")

    def _calculate_next_attempt(self, attempt_count: int) -> datetime:
        """Calculate the next retry attempt time using exponential backoff.

        Formula: min(base_delay * 2^attempt_count, max_delay)

        Args:
            attempt_count: Current attempt count (0-indexed).

        Returns:
            datetime for the next attempt.
        """
        delay = min(
            self.base_delay_seconds * (2**attempt_count),
            self.max_delay_seconds,
        )
        return datetime.now(UTC) + timedelta(seconds=delay)

    async def add_to_retry_queue(
        self,
        event_type: str,
        payload: dict[str, Any],
        error: str,
    ) -> int:
        """Add a failed webhook event to the retry queue.

        The event will be scheduled for retry with exponential backoff.

        Args:
            event_type: Type of webhook event ('merge_request' or 'pipeline').
            payload: Original webhook payload as dict.
            error: Error message from the failed processing attempt.

        Returns:
            ID of the newly created retry queue item.
        """
        now = datetime.now(UTC)
        next_attempt = self._calculate_next_attempt(0)

        log.debug(
            "Adding event to retry queue",
            event_type=event_type,
            next_attempt=next_attempt.isoformat(),
        )

        async with self.db.transaction() as session:
            await session.execute(
                text(_INSERT_RETRY_SQL),
                {
                    "event_type": event_type,
                    "payload": json.dumps(payload),
                    "attempt_count": 0,
                    "max_attempts": self.max_attempts,
                    "next_attempt_at": next_attempt.isoformat(),
                    "last_error": error,
                    "created_at": now.isoformat(),
                },
            )
            # Get the last inserted row ID (SQLite specific)
            result = await session.execute(text("SELECT last_insert_rowid()"))
            retry_id: int = result.scalar_one()

        log.info(
            "Event added to retry queue",
            retry_id=retry_id,
            event_type=event_type,
            next_attempt=next_attempt.isoformat(),
        )
        return retry_id

    async def get_events_ready_for_retry(self, limit: int = 100) -> list[RetryQueueItem]:
        """Get events that are ready to be retried.

        Returns events where next_attempt_at <= now, ordered by next_attempt_at.

        Args:
            limit: Maximum number of items to return (default: 100).

        Returns:
            List of RetryQueueItem objects ready for retry.
        """
        now = datetime.now(UTC)

        async with self.db.session() as session:
            result = await session.execute(
                text(_SELECT_READY_FOR_RETRY_SQL),
                {"now": now.isoformat(), "limit": limit},
            )
            rows = result.mappings().all()
            await session.commit()

        return [self._row_to_retry_item(row) for row in rows]

    async def mark_retry_success(self, retry_id: int) -> None:
        """Mark a retry attempt as successful and remove from queue.

        Args:
            retry_id: ID of the retry queue item.

        Raises:
            RetryItemNotFoundError: If the item doesn't exist.
        """
        log.debug("Marking retry as successful", retry_id=retry_id)

        async with self.db.transaction() as session:
            cursor_result = await session.execute(
                text(_DELETE_RETRY_BY_ID_SQL),
                {"id": retry_id},
            )
            deleted: bool = cursor_result.rowcount > 0  # type: ignore[attr-defined]

        if not deleted:
            raise RetryItemNotFoundError(retry_id)

        log.info("Retry succeeded and removed from queue", retry_id=retry_id)

    async def mark_retry_failed(
        self,
        retry_id: int,
        error: str,
    ) -> bool:
        """Mark a retry attempt as failed.

        If max attempts exceeded, moves to DLQ and returns True.
        Otherwise, schedules next retry and returns False.

        Args:
            retry_id: ID of the retry queue item.
            error: Error message from the failed attempt.

        Returns:
            True if moved to DLQ, False if scheduled for another retry.

        Raises:
            RetryItemNotFoundError: If the item doesn't exist.
        """
        log.debug("Marking retry as failed", retry_id=retry_id)

        # First, get the current item
        async with self.db.session() as session:
            result = await session.execute(
                text(_SELECT_RETRY_BY_ID_SQL),
                {"id": retry_id},
            )
            row = result.mappings().one_or_none()
            await session.commit()

        if row is None:
            raise RetryItemNotFoundError(retry_id)

        current_attempt = row["attempt_count"]
        max_attempts = row["max_attempts"]
        new_attempt_count = current_attempt + 1

        # Check if we've exceeded max attempts
        if new_attempt_count >= max_attempts:
            # Move to DLQ
            await self._move_to_dlq(row, error)
            log.warning(
                "Event moved to DLQ after max retries",
                retry_id=retry_id,
                attempts=new_attempt_count,
                event_type=row["event_type"],
            )
            return True

        # Schedule next retry
        next_attempt = self._calculate_next_attempt(new_attempt_count)

        async with self.db.transaction() as session:
            await session.execute(
                text(_UPDATE_RETRY_ATTEMPT_SQL),
                {
                    "id": retry_id,
                    "attempt_count": new_attempt_count,
                    "next_attempt_at": next_attempt.isoformat(),
                    "last_error": error,
                },
            )

        log.info(
            "Retry failed, scheduled for next attempt",
            retry_id=retry_id,
            attempt=new_attempt_count,
            next_attempt=next_attempt.isoformat(),
        )
        return False

    async def _move_to_dlq(self, row: RowMapping, error: str) -> int:
        """Move a retry queue item to the DLQ.

        Args:
            row: The retry queue item row.
            error: Final error message.

        Returns:
            ID of the newly created DLQ item.
        """
        async with self.db.transaction() as session:
            # Insert into DLQ
            await session.execute(
                text(_INSERT_DLQ_SQL),
                {
                    "event_type": row["event_type"],
                    "payload": row["payload"],
                    "attempt_count": row["attempt_count"] + 1,
                    "last_error": error,
                    "original_created_at": row["created_at"],
                },
            )
            # Get the last inserted row ID (SQLite specific)
            result = await session.execute(text("SELECT last_insert_rowid()"))
            dlq_id: int = result.scalar_one()

            # Delete from retry queue
            await session.execute(
                text(_DELETE_RETRY_BY_ID_SQL),
                {"id": row["id"]},
            )

        return dlq_id

    # =========================================================================
    # DLQ Operations
    # =========================================================================

    async def get_dlq_entries(
        self,
        limit: int = 50,
        offset: int = 0,
        event_type: str | None = None,
    ) -> list[DLQItem]:
        """Get DLQ entries with optional filtering.

        Args:
            limit: Maximum number of items to return.
            offset: Number of items to skip for pagination.
            event_type: Optional filter by event type.

        Returns:
            List of DLQItem objects.
        """
        async with self.db.session() as session:
            if event_type:
                result = await session.execute(
                    text(_SELECT_DLQ_BY_TYPE_SQL),
                    {"event_type": event_type, "limit": limit, "offset": offset},
                )
            else:
                result = await session.execute(
                    text(_SELECT_DLQ_ALL_SQL),
                    {"limit": limit, "offset": offset},
                )
            rows = result.mappings().all()
            await session.commit()

        return [self._row_to_dlq_item(row) for row in rows]

    async def get_dlq_entry(self, entry_id: int) -> DLQItem:
        """Get a single DLQ entry by ID.

        Args:
            entry_id: ID of the DLQ item.

        Returns:
            DLQItem object.

        Raises:
            DLQItemNotFoundError: If the item doesn't exist.
        """
        async with self.db.session() as session:
            result = await session.execute(
                text(_SELECT_DLQ_BY_ID_SQL),
                {"id": entry_id},
            )
            row = result.mappings().one_or_none()
            await session.commit()

        if row is None:
            raise DLQItemNotFoundError(entry_id)

        return self._row_to_dlq_item(row)

    async def delete_dlq_entry(self, entry_id: int) -> bool:
        """Delete a DLQ entry.

        Args:
            entry_id: ID of the DLQ item to delete.

        Returns:
            True if deleted, False if not found.
        """
        async with self.db.transaction() as session:
            cursor_result = await session.execute(
                text(_DELETE_DLQ_BY_ID_SQL),
                {"id": entry_id},
            )
            deleted: bool = cursor_result.rowcount > 0  # type: ignore[attr-defined]

        if deleted:
            log.info("DLQ entry deleted", entry_id=entry_id)
        else:
            log.debug("DLQ entry not found for deletion", entry_id=entry_id)

        return deleted

    async def retry_dlq_entry(self, entry_id: int) -> int:
        """Move a DLQ entry back to the retry queue for another attempt.

        Args:
            entry_id: ID of the DLQ item.

        Returns:
            ID of the new retry queue item.

        Raises:
            DLQItemNotFoundError: If the item doesn't exist.
        """
        log.debug("Retrying DLQ entry", entry_id=entry_id)

        # Get the DLQ item
        async with self.db.session() as session:
            result = await session.execute(
                text(_SELECT_DLQ_BY_ID_SQL),
                {"id": entry_id},
            )
            row = result.mappings().one_or_none()
            await session.commit()

        if row is None:
            raise DLQItemNotFoundError(entry_id)

        # Add back to retry queue with reset attempt count
        now = datetime.now(UTC)
        next_attempt = self._calculate_next_attempt(0)

        async with self.db.transaction() as session:
            # Insert into retry queue
            await session.execute(
                text(_INSERT_RETRY_SQL),
                {
                    "event_type": row["event_type"],
                    "payload": row["payload"],
                    "attempt_count": 0,
                    "max_attempts": self.max_attempts,
                    "next_attempt_at": next_attempt.isoformat(),
                    "last_error": f"Re-queued from DLQ (original error: {row['last_error']})",
                    "created_at": now.isoformat(),
                },
            )
            # Get the last inserted row ID (SQLite specific)
            result = await session.execute(text("SELECT last_insert_rowid()"))
            retry_id: int = result.scalar_one()

            # Delete from DLQ
            await session.execute(
                text(_DELETE_DLQ_BY_ID_SQL),
                {"id": entry_id},
            )

        log.info(
            "DLQ entry moved back to retry queue",
            dlq_entry_id=entry_id,
            retry_id=retry_id,
        )
        return retry_id

    async def get_dlq_stats(self) -> DLQStats:
        """Get statistics about the Dead Letter Queue.

        Returns:
            DLQStats with total count, counts by event type, and oldest entry.
        """
        async with self.db.session() as session:
            # Get total count and oldest entry
            result = await session.execute(text(_SELECT_DLQ_STATS_SQL))
            stats_row = result.mappings().one()

            # Get counts by event type
            result = await session.execute(text(_SELECT_DLQ_BY_TYPE_COUNT_SQL))
            type_rows = result.mappings().all()
            await session.commit()

        by_event_type = {row["event_type"]: row["count"] for row in type_rows}

        oldest_entry = stats_row["oldest_entry"]
        if isinstance(oldest_entry, str):
            oldest_entry = datetime.fromisoformat(oldest_entry)

        return DLQStats(
            total_count=stats_row["total_count"],
            by_event_type=by_event_type,
            oldest_entry=oldest_entry,
        )

    async def cleanup_old_dlq_entries(self, days: int = 30) -> int:
        """Remove DLQ entries older than specified days.

        Args:
            days: Number of days after which to delete entries (default: 30).

        Returns:
            Number of entries deleted.
        """
        log.debug("Cleaning up old DLQ entries", days=days)

        async with self.db.transaction() as session:
            cursor_result = await session.execute(
                text(_CLEANUP_OLD_DLQ_SQL),
                {"days_param": f"-{days} days"},
            )
            deleted_count: int = cursor_result.rowcount  # type: ignore[attr-defined]

        if deleted_count > 0:
            log.info(
                "Old DLQ entries cleaned up",
                deleted_count=deleted_count,
                days=days,
            )
        else:
            log.debug("No old DLQ entries to clean up")

        return deleted_count

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _row_to_retry_item(self, row: RowMapping | dict[str, Any]) -> RetryQueueItem:
        """Convert a database row to a RetryQueueItem."""
        next_attempt_at = row["next_attempt_at"]
        if isinstance(next_attempt_at, str):
            next_attempt_at = datetime.fromisoformat(next_attempt_at)

        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)

        return RetryQueueItem(
            id=row["id"],
            event_type=row["event_type"],
            payload=payload,
            attempt_count=row["attempt_count"],
            max_attempts=row["max_attempts"],
            next_attempt_at=next_attempt_at,
            created_at=created_at,
            last_error=row.get("last_error"),
        )

    def _row_to_dlq_item(self, row: RowMapping | dict[str, Any]) -> DLQItem:
        """Convert a database row to a DLQItem."""
        original_created_at = row["original_created_at"]
        if isinstance(original_created_at, str):
            original_created_at = datetime.fromisoformat(original_created_at)

        moved_to_dlq_at = row["moved_to_dlq_at"]
        if isinstance(moved_to_dlq_at, str):
            moved_to_dlq_at = datetime.fromisoformat(moved_to_dlq_at)

        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)

        return DLQItem(
            id=row["id"],
            event_type=row["event_type"],
            payload=payload,
            attempt_count=row["attempt_count"],
            last_error=row["last_error"],
            original_created_at=original_created_at,
            moved_to_dlq_at=moved_to_dlq_at,
        )


__all__: list[str] = [
    "DLQItemNotFoundError",
    "RetryItemNotFoundError",
    "RetryQueueError",
    "WebhookRetryManager",
]
