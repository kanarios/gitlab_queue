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

from gitlab_queue.db.time_sql import epoch_sql
from gitlab_queue.models.retry import DLQItem, DLQStats, RetryQueueItem
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

    from sqlalchemy import RowMapping
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import TextClause

    from gitlab_queue.db.database import Database

log = get_logger(__name__)


# =============================================================================
# SQL Statements
# =============================================================================

_INSERT_RETRY_SQL = """
INSERT INTO webhook_retry_queue (
    project_id, event_type, payload, attempt_count, max_attempts, next_attempt_at, last_error, created_at
)
VALUES (
    :project_id, :event_type, :payload, :attempt_count, :max_attempts, :next_attempt_at, :last_error, :created_at
)
"""

_SELECT_READY_FOR_RETRY_SQL = """
SELECT * FROM webhook_retry_queue
WHERE {next_epoch} <= :now
  AND (CAST(:project_id AS INTEGER) IS NULL OR project_id = :project_id)
{excluded_projects_clause}
ORDER BY {next_epoch} ASC, id ASC
LIMIT :limit
"""

_SELECT_RETRY_BY_ID_SQL = """
SELECT * FROM webhook_retry_queue
WHERE id = :id AND (CAST(:project_id AS INTEGER) IS NULL OR project_id = :project_id)
"""

_DELETE_RETRY_BY_ID_SQL = """
DELETE FROM webhook_retry_queue
WHERE id = :id AND (CAST(:project_id AS INTEGER) IS NULL OR project_id = :project_id)
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
    project_id, event_type, payload, attempt_count, last_error, original_created_at, moved_to_dlq_at
)
VALUES (
    :project_id, :event_type, :payload, :attempt_count, :last_error, :original_created_at, :moved_to_dlq_at
)
"""

_SELECT_DLQ_ALL_SQL = """
SELECT * FROM webhook_dlq
WHERE (CAST(:project_id AS INTEGER) IS NULL OR project_id = :project_id)
ORDER BY {moved_epoch} DESC, id DESC
LIMIT :limit OFFSET :offset
"""

_SELECT_DLQ_BY_TYPE_SQL = """
SELECT * FROM webhook_dlq
WHERE event_type = :event_type
  AND (CAST(:project_id AS INTEGER) IS NULL OR project_id = :project_id)
ORDER BY {moved_epoch} DESC, id DESC
LIMIT :limit OFFSET :offset
"""

_SELECT_DLQ_BY_ID_SQL = """
SELECT * FROM webhook_dlq
WHERE id = :id AND (CAST(:project_id AS INTEGER) IS NULL OR project_id = :project_id)
"""

_DELETE_DLQ_BY_ID_SQL = """
DELETE FROM webhook_dlq
WHERE id = :id AND (CAST(:project_id AS INTEGER) IS NULL OR project_id = :project_id)
"""

_SELECT_DLQ_STATS_SQL = """
SELECT
    COUNT(*) as total_count,
    MIN({moved_epoch}) as oldest_entry
FROM webhook_dlq
WHERE (CAST(:project_id AS INTEGER) IS NULL OR project_id = :project_id)
"""

_SELECT_DLQ_BY_TYPE_COUNT_SQL = """
SELECT event_type, COUNT(*) as count
FROM webhook_dlq
WHERE (CAST(:project_id AS INTEGER) IS NULL OR project_id = :project_id)
GROUP BY event_type
"""

_CLEANUP_OLD_DLQ_SQL = """
DELETE FROM webhook_dlq
WHERE {moved_epoch} < :cutoff
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


def _utc_now() -> datetime:
    return datetime.now(UTC)


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
    clock: Callable[[], datetime] = _utc_now

    async def ensure_schema(self) -> None:
        """Create retry queue and DLQ tables if they don't exist.

        Safe to call multiple times - uses CREATE IF NOT EXISTS.
        """
        log.debug("Ensuring retry queue schema exists")

        await self.db.ensure_schema()

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
        return self.clock() + timedelta(seconds=delay)

    async def add_to_retry_queue(
        self,
        event_type: str,
        payload: dict[str, Any],
        error: str,
        project_id: int = 0,
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
        now = self.clock()
        next_attempt = self._calculate_next_attempt(0)

        log.debug(
            "Adding event to retry queue",
            event_type=event_type,
            next_attempt=next_attempt.isoformat(),
        )

        async with self.db.transaction() as session:
            result = await session.execute(
                text(_INSERT_RETRY_SQL + " RETURNING id"),
                {
                    "event_type": event_type,
                    "project_id": project_id,
                    "payload": json.dumps(payload),
                    "attempt_count": 0,
                    "max_attempts": self.max_attempts,
                    "next_attempt_at": next_attempt.isoformat(),
                    "last_error": error,
                    "created_at": now.isoformat(),
                },
            )
            retry_id: int = result.scalar_one()

        log.info(
            "Event added to retry queue",
            retry_id=retry_id,
            event_type=event_type,
            next_attempt=next_attempt.isoformat(),
        )
        return retry_id

    async def get_events_ready_for_retry(
        self,
        limit: int = 100,
        project_id: int | None = None,
        excluded_project_ids: Collection[int] | None = None,
    ) -> list[RetryQueueItem]:
        """Get events that are ready to be retried.

        Returns events where next_attempt_at <= now, ordered by next_attempt_at.

        Args:
            limit: Maximum number of items to return (default: 100).
            project_id: Optional project ID to include exclusively.
            excluded_project_ids: Optional project IDs to exclude from results.

        Returns:
            List of RetryQueueItem objects ready for retry.
        """
        now = self.clock()
        params: dict[str, Any] = {"now": now.timestamp(), "limit": limit, "project_id": project_id}
        excluded_projects_clause = ""
        if excluded_project_ids:
            placeholders = []
            for index, excluded_project_id in enumerate(excluded_project_ids):
                placeholder = f"excluded_project_id_{index}"
                placeholders.append(f":{placeholder}")
                params[placeholder] = excluded_project_id
            excluded_projects_clause = f"\n  AND project_id NOT IN ({', '.join(placeholders)})"

        async with self.db.session() as session:
            result = await session.execute(
                self._time_sql(_SELECT_READY_FOR_RETRY_SQL, excluded_projects_clause=excluded_projects_clause),
                params,
            )
            rows = result.mappings().all()
            await session.commit()

        return [self._row_to_retry_item(row) for row in rows]

    async def move_retry_to_dlq(self, retry_id: int, error: str, project_id: int) -> None:
        """Move a retry item directly to the DLQ without another processing attempt.

        This is for events that cannot be processed anymore, such as retries
        belonging to a project that has been removed from the active config.
        """
        async with self.db.session() as session:
            result = await session.execute(
                text(_SELECT_RETRY_BY_ID_SQL),
                {"id": retry_id, "project_id": project_id},
            )
            row = result.mappings().one_or_none()
            await session.commit()

        if row is None:
            raise RetryItemNotFoundError(retry_id)

        await self._move_to_dlq(row, error, increment_attempt=False)
        log.warning(
            "Retry item moved to DLQ because its project is no longer configured",
            retry_id=retry_id,
            project_id=project_id,
        )

    async def mark_retry_success(self, retry_id: int, project_id: int | None = None) -> None:
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
                {"id": retry_id, "project_id": project_id},
            )
            deleted: bool = cursor_result.rowcount > 0  # type: ignore[attr-defined]

        if not deleted:
            raise RetryItemNotFoundError(retry_id)

        log.info("Retry succeeded and removed from queue", retry_id=retry_id)

    async def mark_retry_failed(self, retry_id: int, error: str, project_id: int | None = None) -> bool:
        """Atomically increment the attempt and reschedule or move the owned row."""
        async with self.db.transaction() as session:
            result = await session.execute(
                text(
                    "UPDATE webhook_retry_queue SET attempt_count = attempt_count + 1, last_error = :error "
                    "WHERE id = :id AND (CAST(:project_id AS INTEGER) IS NULL OR project_id = :project_id) RETURNING *"
                ),
                {"id": retry_id, "project_id": project_id, "error": error},
            )
            row = result.mappings().one_or_none()
            if row is None:
                raise RetryItemNotFoundError(retry_id)
            if row["attempt_count"] >= row["max_attempts"]:
                await self._move_row_to_dlq(session, row, error, increment_attempt=False)
                return True
            await session.execute(
                text(_UPDATE_RETRY_ATTEMPT_SQL),
                {
                    "id": retry_id,
                    "attempt_count": row["attempt_count"],
                    "next_attempt_at": self._calculate_next_attempt(row["attempt_count"]).isoformat(),
                    "last_error": error,
                },
            )
        return False

    async def _move_to_dlq(self, row: RowMapping, error: str, *, increment_attempt: bool = True) -> int:
        async with self.db.transaction() as session:
            return await self._move_row_to_dlq(session, row, error, increment_attempt=increment_attempt)

    async def _move_row_to_dlq(
        self, session: AsyncSession, row: RowMapping, error: str, *, increment_attempt: bool
    ) -> int:
        result = await session.execute(
            text(_DELETE_RETRY_BY_ID_SQL), {"id": row["id"], "project_id": row["project_id"]}
        )
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise RetryItemNotFoundError(int(row["id"]))
        result = await session.execute(
            text(_INSERT_DLQ_SQL + " RETURNING id"),
            {
                "event_type": row["event_type"],
                "project_id": row["project_id"],
                "payload": row["payload"],
                "attempt_count": row["attempt_count"] + int(increment_attempt),
                "last_error": error,
                "original_created_at": row["created_at"],
                "moved_to_dlq_at": self.clock().isoformat(),
            },
        )
        return int(result.scalar_one())

    # =========================================================================
    # DLQ Operations
    # =========================================================================

    async def get_dlq_entries(
        self,
        limit: int = 50,
        offset: int = 0,
        event_type: str | None = None,
        project_id: int | None = None,
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
                    self._time_sql(_SELECT_DLQ_BY_TYPE_SQL),
                    {
                        "event_type": event_type,
                        "limit": limit,
                        "offset": offset,
                        "project_id": project_id,
                    },
                )
            else:
                result = await session.execute(
                    self._time_sql(_SELECT_DLQ_ALL_SQL),
                    {"limit": limit, "offset": offset, "project_id": project_id},
                )
            rows = result.mappings().all()
            await session.commit()

        return [self._row_to_dlq_item(row) for row in rows]

    async def get_dlq_entry(self, entry_id: int, project_id: int | None = None) -> DLQItem:
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
                {"id": entry_id, "project_id": project_id},
            )
            row = result.mappings().one_or_none()
            await session.commit()

        if row is None:
            raise DLQItemNotFoundError(entry_id)

        return self._row_to_dlq_item(row)

    async def delete_dlq_entry(self, entry_id: int, project_id: int | None = None) -> bool:
        """Delete a DLQ entry.

        Args:
            entry_id: ID of the DLQ item to delete.

        Returns:
            True if deleted, False if not found.
        """
        async with self.db.transaction() as session:
            cursor_result = await session.execute(
                text(_DELETE_DLQ_BY_ID_SQL),
                {"id": entry_id, "project_id": project_id},
            )
            deleted: bool = cursor_result.rowcount > 0  # type: ignore[attr-defined]

        if deleted:
            log.info("DLQ entry deleted", entry_id=entry_id)
        else:
            log.debug("DLQ entry not found for deletion", entry_id=entry_id)

        return deleted

    async def retry_dlq_entry(self, entry_id: int, project_id: int | None = None) -> int:
        """Atomically claim one DLQ row before inserting its reset retry."""
        async with self.db.transaction() as session:
            result = await session.execute(
                text(_DELETE_DLQ_BY_ID_SQL + " RETURNING *"), {"id": entry_id, "project_id": project_id}
            )
            row = result.mappings().one_or_none()
            if row is None:
                raise DLQItemNotFoundError(entry_id)
            result = await session.execute(
                text(_INSERT_RETRY_SQL + " RETURNING id"),
                {
                    "event_type": row["event_type"],
                    "project_id": row["project_id"],
                    "payload": row["payload"],
                    "attempt_count": 0,
                    "max_attempts": self.max_attempts,
                    "next_attempt_at": self._calculate_next_attempt(0).isoformat(),
                    "last_error": f"Re-queued from DLQ (original error: {row['last_error']})",
                    "created_at": self.clock().isoformat(),
                },
            )
            return int(result.scalar_one())

    async def get_dlq_stats(self, project_id: int | None = None) -> DLQStats:
        """Get statistics about the Dead Letter Queue.

        Returns:
            DLQStats with total count, counts by event type, and oldest entry.
        """
        async with self.db.session() as session:
            # Get total count and oldest entry
            result = await session.execute(self._time_sql(_SELECT_DLQ_STATS_SQL), {"project_id": project_id})
            stats_row = result.mappings().one()

            # Get counts by event type
            result = await session.execute(text(_SELECT_DLQ_BY_TYPE_COUNT_SQL), {"project_id": project_id})
            type_rows = result.mappings().all()
            await session.commit()

        by_event_type = {row["event_type"]: row["count"] for row in type_rows}

        oldest_entry = stats_row["oldest_entry"]
        if oldest_entry is not None:
            oldest_entry = datetime.fromtimestamp(float(oldest_entry), UTC)

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
                self._time_sql(_CLEANUP_OLD_DLQ_SQL),
                {"cutoff": (self.clock() - timedelta(days=days)).timestamp()},
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

    def _time_sql(self, template: str, **values: str) -> TextClause:
        backend = self.db.engine.dialect.name
        return text(
            template.format(
                next_epoch=epoch_sql("next_attempt_at", backend),
                moved_epoch=epoch_sql("moved_to_dlq_at", backend),
                **values,
            )
        )

    def _row_to_retry_item(self, row: RowMapping | dict[str, Any]) -> RetryQueueItem:
        """Convert a database row to a RetryQueueItem."""
        next_attempt_at = row["next_attempt_at"]
        if isinstance(next_attempt_at, str):
            next_attempt_at = datetime.fromisoformat(next_attempt_at)
        if next_attempt_at.tzinfo is None:
            next_attempt_at = next_attempt_at.replace(tzinfo=UTC)

        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        if created_at is not None and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

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
            project_id=row.get("project_id", 0),
            last_error=row.get("last_error"),
        )

    def _row_to_dlq_item(self, row: RowMapping | dict[str, Any]) -> DLQItem:
        """Convert a database row to a DLQItem."""
        original_created_at = row["original_created_at"]
        if isinstance(original_created_at, str):
            original_created_at = datetime.fromisoformat(original_created_at)
        if original_created_at is not None and original_created_at.tzinfo is None:
            original_created_at = original_created_at.replace(tzinfo=UTC)

        moved_to_dlq_at = row["moved_to_dlq_at"]
        if isinstance(moved_to_dlq_at, str):
            moved_to_dlq_at = datetime.fromisoformat(moved_to_dlq_at)
        if moved_to_dlq_at is not None and moved_to_dlq_at.tzinfo is None:
            moved_to_dlq_at = moved_to_dlq_at.replace(tzinfo=UTC)

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
            project_id=row.get("project_id", 0),
        )


__all__: list[str] = [
    "DLQItemNotFoundError",
    "RetryItemNotFoundError",
    "RetryQueueError",
    "WebhookRetryManager",
]
