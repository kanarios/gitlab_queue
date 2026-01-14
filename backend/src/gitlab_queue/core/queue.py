"""Queue Manager for GitLab Merge Queue Bot.

Manages the merge request queue with SQLite storage, providing
FIFO ordering with hotfix priority support.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from gitlab_queue.metrics import OPERATIONS_TOTAL
from gitlab_queue.models.queue_item import DashboardStats, QueueItem
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy import RowMapping

    from gitlab_queue.db.database import Database
    from gitlab_queue.models.mr import MergeRequest

log = get_logger(__name__)


# =============================================================================
# SQL Statements
# =============================================================================

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS merge_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    iid INTEGER NOT NULL UNIQUE,
    title TEXT NOT NULL,
    author_name TEXT NOT NULL,
    author_username TEXT NOT NULL,
    author_avatar TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    is_hotfix INTEGER DEFAULT 0,
    labels TEXT,
    target_branch TEXT NOT NULL,
    queued_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    pipeline_id INTEGER,
    pipeline_status TEXT,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    stale_warning_sent INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_mr_status ON merge_requests(status)",
    "CREATE INDEX IF NOT EXISTS idx_mr_queued_at ON merge_requests(queued_at)",
    "CREATE INDEX IF NOT EXISTS idx_mr_iid ON merge_requests(iid)",
    "CREATE INDEX IF NOT EXISTS idx_mr_finished_at ON merge_requests(finished_at)",
]

_INSERT_MR_SQL = """
INSERT INTO merge_requests (
    iid, title, author_name, author_username, author_avatar,
    status, is_hotfix, labels, target_branch, queued_at
)
VALUES (
    :iid, :title, :author_name, :author_username, :author_avatar,
    'queued', :is_hotfix, :labels, :target_branch, :queued_at
)
ON CONFLICT(iid) DO NOTHING
"""

_SELECT_MR_BY_IID_SQL = """
SELECT * FROM merge_requests WHERE iid = :iid
"""

_SELECT_ACTIVE_QUEUE_SQL = """
SELECT * FROM merge_requests
WHERE status IN ('queued', 'rebasing', 'testing', 'merging')
ORDER BY is_hotfix DESC, queued_at ASC
"""

_SELECT_NEXT_MR_SQL = """
SELECT * FROM merge_requests
WHERE status = 'queued'
ORDER BY is_hotfix DESC, queued_at ASC
LIMIT 1
"""

_UPDATE_STATUS_SQL = """
UPDATE merge_requests
SET status = :status
WHERE iid = :iid AND status != :status
"""

_COUNT_POSITION_SQL = """
SELECT COUNT(*) FROM merge_requests
WHERE status IN ('queued', 'rebasing', 'testing', 'merging')
AND (
    is_hotfix > (SELECT COALESCE(is_hotfix, 0) FROM merge_requests WHERE iid = :iid)
    OR (
        is_hotfix = (SELECT COALESCE(is_hotfix, 0) FROM merge_requests WHERE iid = :iid)
        AND queued_at < (SELECT queued_at FROM merge_requests WHERE iid = :iid)
    )
)
"""

_SELECT_MR_STATE_SQL = """
SELECT status, started_at, last_error, finished_at FROM merge_requests WHERE iid = :iid
"""

_SELECT_QUEUE_STATS_SQL = """
SELECT status, COUNT(*) as count FROM merge_requests
WHERE status IN ('queued', 'rebasing', 'testing', 'merging')
GROUP BY status
"""

_CLEANUP_OLD_ENTRIES_SQL = """
DELETE FROM merge_requests
WHERE finished_at IS NOT NULL AND finished_at < datetime('now', :days_param)
"""

_SELECT_STALE_MRS_SQL = """
SELECT * FROM merge_requests
WHERE status IN ('queued', 'rebasing', 'testing', 'merging')
AND stale_warning_sent = 0
AND queued_at < datetime('now', :hours_param)
ORDER BY queued_at ASC
"""

_MARK_STALE_WARNING_SENT_SQL = """
UPDATE merge_requests
SET stale_warning_sent = 1
WHERE iid = :iid
"""

_ALTER_TABLE_STALE_WARNING_SQL = """
ALTER TABLE merge_requests ADD COLUMN stale_warning_sent INTEGER DEFAULT 0
"""

_SELECT_RECENT_HISTORY_SQL = """
SELECT * FROM merge_requests
WHERE status IN ('merged', 'failed', 'removed')
AND finished_at IS NOT NULL
ORDER BY finished_at DESC
LIMIT :limit
"""

_SELECT_STATS_WINDOW_SQL = """
SELECT
    SUM(CASE WHEN status = 'merged' THEN 1 ELSE 0 END) as merged_count,
    SUM(CASE WHEN status IN ('merged', 'failed') THEN 1 ELSE 0 END) as total_completed,
    AVG(CASE WHEN started_at IS NOT NULL AND queued_at IS NOT NULL THEN
        (julianday(started_at) - julianday(queued_at)) * 86400 ELSE NULL END
    ) as avg_wait_seconds,
    AVG(CASE WHEN finished_at IS NOT NULL AND started_at IS NOT NULL AND status = 'merged' THEN
        (julianday(finished_at) - julianday(started_at)) * 86400 ELSE NULL END
    ) as avg_processing_seconds
FROM merge_requests
WHERE finished_at >= datetime('now', :days_param)
"""


# =============================================================================
# Custom Exceptions
# =============================================================================


class QueueError(Exception):
    """Base exception for queue operations."""


class QueueItemNotFoundError(QueueError):
    """Raised when a queue item is not found."""

    def __init__(self, mr_iid: int) -> None:
        self.mr_iid = mr_iid
        super().__init__(f"Queue item not found: MR !{mr_iid}")


# =============================================================================
# Queue Cache
# =============================================================================


@dataclass
class QueueCache:
    """In-memory cache for active queue state.

    Caches the active queue to avoid repeated database queries.
    Cache is invalidated on any write operation.

    Attributes:
        _active_queue: Cached list of active queue items, or None if invalid.
        _last_refresh: Timestamp of last cache refresh.
    """

    _active_queue: list[QueueItem] | None = field(default=None)
    _last_refresh: datetime | None = field(default=None)

    def invalidate(self) -> None:
        """Clear all cached data."""
        self._active_queue = None
        self._last_refresh = None

    @property
    def is_valid(self) -> bool:
        """Check if cache contains valid data."""
        return self._active_queue is not None

    def get_active_queue(self) -> list[QueueItem] | None:
        """Get cached active queue or None if cache is invalid."""
        return self._active_queue

    def set_active_queue(self, items: list[QueueItem]) -> None:
        """Update cached active queue."""
        self._active_queue = items
        self._last_refresh = datetime.now(UTC)


# =============================================================================
# Queue Manager
# =============================================================================


@dataclass
class QueueManager:
    """Manages the merge request queue in SQLite.

    Provides FIFO ordering with hotfix priority support. All operations
    are idempotent and transaction-safe. Uses an in-memory cache for
    active queue to reduce database queries.

    Attributes:
        db: Database instance for SQLite operations.
        _cache: In-memory cache for active queue state.

    Example:
        >>> from gitlab_queue.db.database import Database
        >>> async with Database("sqlite+aiosqlite:///data/queue.db") as db:
        ...     queue = QueueManager(db)
        ...     await queue.ensure_schema()
        ...     await queue.add_to_queue(mr, is_hotfix=False)
    """

    db: Database
    _cache: QueueCache = field(default_factory=QueueCache, init=False)

    async def ensure_schema(self) -> None:
        """Create the merge_requests table and indexes if they don't exist.

        Safe to call multiple times - uses CREATE IF NOT EXISTS.
        Also handles schema migrations for new columns.
        """
        log.debug("Ensuring database schema exists")

        async with self.db.transaction() as session:
            await session.execute(text(_CREATE_TABLE_SQL))
            for index_sql in _CREATE_INDEXES_SQL:
                await session.execute(text(index_sql))

            # Migrate: add stale_warning_sent column if not exists
            try:
                await session.execute(text(_ALTER_TABLE_STALE_WARNING_SQL))
                log.info("Added stale_warning_sent column to merge_requests table")
            except Exception:
                # Column already exists - ignore
                pass

        log.info("Database schema ensured")

    async def add_to_queue(
        self,
        mr: MergeRequest,
        is_hotfix: bool = False,
    ) -> QueueItem:
        """Add a merge request to the queue.

        Idempotent - if the MR is already in the queue, returns the existing item.
        New items are added with 'queued' status.

        Args:
            mr: The MergeRequest to add.
            is_hotfix: Whether this MR has hotfix priority.

        Returns:
            QueueItem representing the MR in the queue.
        """
        now = datetime.now(UTC)
        labels_json = json.dumps(mr.labels)

        log.debug(
            "Adding MR to queue",
            mr_iid=mr.iid,
            is_hotfix=is_hotfix,
            title=mr.title,
        )

        async with self.db.transaction() as session:
            # Try to insert (will be ignored if already exists)
            await session.execute(
                text(_INSERT_MR_SQL),
                {
                    "iid": mr.iid,
                    "title": mr.title,
                    "author_name": mr.author.name,
                    "author_username": mr.author.username,
                    "author_avatar": mr.author.avatar_url,
                    "is_hotfix": 1 if is_hotfix else 0,
                    "labels": labels_json,
                    "target_branch": mr.target_branch,
                    "queued_at": now.isoformat(),
                },
            )

            # Fetch the item (whether newly inserted or existing)
            result = await session.execute(
                text(_SELECT_MR_BY_IID_SQL),
                {"iid": mr.iid},
            )
            row = result.mappings().one()

        item = self._row_to_queue_item(row)
        self._cache.invalidate()  # Invalidate cache after queue modification
        OPERATIONS_TOTAL.labels(type="add", status="success").inc()
        log.info(
            "MR added to queue",
            mr_iid=mr.iid,
            state=item.state,
            is_hotfix=item.is_hotfix,
        )
        return item

    async def remove_from_queue(self, mr_iid: int) -> bool:
        """Remove a merge request from the queue by setting status to 'removed'.

        Idempotent - returns True if status was changed, False if already removed
        or not found.

        Args:
            mr_iid: The MR's internal ID.

        Returns:
            True if the MR was removed, False if already removed or not found.
        """
        log.debug("Removing MR from queue", mr_iid=mr_iid)

        async with self.db.transaction() as session:
            cursor_result = await session.execute(
                text(_UPDATE_STATUS_SQL),
                {"iid": mr_iid, "status": "removed"},
            )
            # CursorResult has rowcount for DML statements
            changed: bool = cursor_result.rowcount > 0  # type: ignore[attr-defined]

        if changed:
            self._cache.invalidate()  # Invalidate cache after queue modification
            OPERATIONS_TOTAL.labels(type="remove", status="success").inc()
            log.info("MR removed from queue", mr_iid=mr_iid)
        else:
            log.debug("MR not removed (already removed or not found)", mr_iid=mr_iid)

        return changed

    async def get_queue_position(self, mr_iid: int) -> int | None:
        """Get the position of an MR in the active queue.

        Position is 1-indexed (first MR in queue = position 1).
        Considers hotfix priority in ordering. Uses in-memory cache
        via get_active_queue().

        Args:
            mr_iid: The MR's internal ID.

        Returns:
            Position (1-indexed) if in active queue, None if not found or removed.
        """
        queue = await self.get_active_queue()
        for i, item in enumerate(queue):
            if item.mr_iid == mr_iid:
                return i + 1  # 1-indexed
        return None

    async def get_next_mr(self) -> QueueItem | None:
        """Get the next MR to process from the queue.

        Returns the first MR with status 'queued', ordered by:
        1. is_hotfix DESC (hotfixes first)
        2. queued_at ASC (FIFO within priority)

        Uses in-memory cache via get_active_queue().

        Returns:
            Next QueueItem to process, or None if queue is empty.
        """
        queue = await self.get_active_queue()
        for item in queue:
            if item.state == "queued":
                return item
        return None

    async def get_queue_item(self, mr_iid: int) -> QueueItem | None:
        """Get a queue item by MR IID.

        Args:
            mr_iid: The MR's internal ID.

        Returns:
            QueueItem if found, None otherwise.
        """
        async with self.db.session() as session:
            result = await session.execute(
                text(_SELECT_MR_BY_IID_SQL),
                {"iid": mr_iid},
            )
            row = result.mappings().one_or_none()
            await session.commit()

        if row is None:
            return None

        return self._row_to_queue_item(row)

    async def get_active_queue(self) -> list[QueueItem]:
        """Get all MRs in the active queue.

        Returns MRs with status in ('queued', 'rebasing', 'testing', 'merging'),
        ordered by hotfix priority and queue time. Uses in-memory cache when available.

        Returns:
            List of QueueItems in queue order.
        """
        # Return cached data if available
        cached = self._cache.get_active_queue()
        if cached is not None:
            return cached

        # Fetch from database and cache
        async with self.db.session() as session:
            result = await session.execute(text(_SELECT_ACTIVE_QUEUE_SQL))
            rows = result.mappings().all()
            await session.commit()

        items = [self._row_to_queue_item(row) for row in rows]
        self._cache.set_active_queue(items)
        return items

    async def get_queue_length(self) -> int:
        """Get the number of MRs in the active queue.

        Returns:
            Number of MRs with active status.
        """
        items = await self.get_active_queue()
        return len(items)

    async def get_mr_state(self, mr_iid: int) -> dict[str, Any] | None:
        """Get the current state of an MR in the queue.

        Args:
            mr_iid: The MR's internal ID.

        Returns:
            Dict with status, started_at, last_error, finished_at or None if not found.
        """
        async with self.db.session() as session:
            result = await session.execute(
                text(_SELECT_MR_STATE_SQL),
                {"iid": mr_iid},
            )
            row = result.mappings().one_or_none()
            await session.commit()

        if row is None:
            return None

        return {
            "status": row["status"],
            "started_at": (
                datetime.fromisoformat(row["started_at"]) if row["started_at"] else None
            ),
            "last_error": row["last_error"],
            "finished_at": (
                datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None
            ),
        }

    async def update_mr_state(
        self,
        mr_iid: int,
        state: str,
        **extra: Any,
    ) -> bool:
        """Update the state of an MR in the queue.

        Sets started_at automatically on first state change from 'queued'.
        Sets finished_at automatically for terminal states (merged, failed, removed).

        Args:
            mr_iid: The MR's internal ID.
            state: New state to set.
            **extra: Additional fields to update (pipeline_id, pipeline_status,
                last_error, retry_count).

        Returns:
            True if updated.

        Raises:
            QueueItemNotFoundError: If MR not in queue.
        """
        log.debug("Updating MR state", mr_iid=mr_iid, new_state=state, extra=extra)

        now = datetime.now(UTC)
        terminal_states = ("merged", "failed", "removed")

        # Build dynamic UPDATE query
        set_clauses = ["status = :status"]
        params: dict[str, Any] = {"iid": mr_iid, "status": state}

        # Auto-set started_at if transitioning from queued
        set_clauses.append("started_at = COALESCE(started_at, :started_at)")
        params["started_at"] = now.isoformat()

        # Auto-set finished_at for terminal states
        if state in terminal_states:
            set_clauses.append("finished_at = COALESCE(finished_at, :finished_at)")
            params["finished_at"] = now.isoformat()

        # Handle extra fields
        allowed_fields = ("pipeline_id", "pipeline_status", "last_error", "retry_count")
        for field_name, value in extra.items():
            if field_name in allowed_fields:
                set_clauses.append(f"{field_name} = :{field_name}")
                params[field_name] = value

        sql = f"UPDATE merge_requests SET {', '.join(set_clauses)} WHERE iid = :iid"

        async with self.db.transaction() as session:
            cursor_result = await session.execute(text(sql), params)
            changed: bool = cursor_result.rowcount > 0  # type: ignore[attr-defined]

        if changed:
            self._cache.invalidate()  # Invalidate cache after state change
            OPERATIONS_TOTAL.labels(type="update", status="success").inc()
            log.info("MR state updated", mr_iid=mr_iid, new_state=state)
        else:
            log.warning("MR not found for state update", mr_iid=mr_iid)
            raise QueueItemNotFoundError(mr_iid)

        return changed

    async def get_queue_stats(self) -> dict[str, int]:
        """Get statistics about the active queue.

        Returns:
            Dict mapping status to count for active states.
            Example: {"queued": 5, "rebasing": 1, "testing": 2, "merging": 0}
        """
        async with self.db.session() as session:
            result = await session.execute(text(_SELECT_QUEUE_STATS_SQL))
            rows = result.mappings().all()
            await session.commit()

        # Initialize all active states with 0
        stats: dict[str, int] = {
            "queued": 0,
            "rebasing": 0,
            "testing": 0,
            "merging": 0,
        }

        # Fill in actual counts
        for row in rows:
            stats[row["status"]] = row["count"]

        log.debug("Queue stats retrieved", stats=stats)
        return stats

    async def get_recent_history(self, limit: int = 10) -> list[QueueItem]:
        """Get recently completed MRs for dashboard history.

        Returns MRs with status in ('merged', 'failed', 'removed') that have
        a finished_at timestamp, ordered by most recent first.

        Args:
            limit: Maximum number of items to return (default: 10).

        Returns:
            List of QueueItems ordered by finished_at descending.
        """
        log.debug("Getting recent history", limit=limit)

        async with self.db.session() as session:
            result = await session.execute(
                text(_SELECT_RECENT_HISTORY_SQL),
                {"limit": limit},
            )
            rows = result.mappings().all()
            await session.commit()

        history = [self._row_to_queue_item(row) for row in rows]
        log.debug("Recent history retrieved", count=len(history))
        return history

    async def get_dashboard_stats(self, days: int = 7) -> DashboardStats:
        """Get aggregate statistics for dashboard display.

        Computes statistics over a rolling window of completed MRs.

        Args:
            days: Number of days to include in statistics (default: 7).

        Returns:
            DashboardStats with success rate and timing metrics.
        """
        log.debug("Getting dashboard stats", days=days)

        async with self.db.session() as session:
            result = await session.execute(
                text(_SELECT_STATS_WINDOW_SQL),
                {"days_param": f"-{days} days"},
            )
            row = result.mappings().one()
            await session.commit()

        merged_count = int(row["merged_count"] or 0)
        total_completed = int(row["total_completed"] or 0)
        success_rate = (merged_count / total_completed * 100) if total_completed > 0 else 0.0

        total_in_queue = await self.get_queue_length()

        stats = DashboardStats(
            total_in_queue=total_in_queue,
            merged_count=merged_count,
            failed_count=total_completed - merged_count,
            success_rate=round(success_rate, 1),
            avg_wait_seconds=round(float(row["avg_wait_seconds"] or 0), 1),
            avg_processing_seconds=round(float(row["avg_processing_seconds"] or 0), 1),
            stats_window_days=days,
        )

        log.debug("Dashboard stats retrieved", stats=stats)
        return stats

    async def cleanup_old_entries(self, days: int = 90) -> int:
        """Delete queue entries older than specified days.

        Only deletes entries that have a finished_at timestamp (completed MRs).
        Active MRs are never deleted regardless of age.

        Args:
            days: Number of days after which to delete entries (default: 90).

        Returns:
            Number of entries deleted.
        """
        log.debug("Cleaning up old queue entries", days=days)

        async with self.db.transaction() as session:
            cursor_result = await session.execute(
                text(_CLEANUP_OLD_ENTRIES_SQL),
                {"days_param": f"-{days} days"},
            )
            deleted_count: int = cursor_result.rowcount  # type: ignore[attr-defined]

        if deleted_count > 0:
            log.info("Old queue entries cleaned up", deleted_count=deleted_count, days=days)
        else:
            log.debug("No old entries to clean up")

        return deleted_count

    async def get_stale_mrs(self, hours: int) -> list[QueueItem]:
        """Get MRs that have been in queue longer than specified hours.

        Only returns MRs that haven't received a stale warning yet.

        Args:
            hours: Threshold in hours.

        Returns:
            List of QueueItem objects that exceed the threshold and haven't been warned.
        """
        log.debug("Checking for stale MRs", hours=hours)

        async with self.db.session() as session:
            result = await session.execute(
                text(_SELECT_STALE_MRS_SQL),
                {"hours_param": f"-{hours} hours"},
            )
            rows = result.mappings().all()
            await session.commit()

        stale_items = [self._row_to_queue_item(row) for row in rows]

        if stale_items:
            log.info(
                "Found stale MRs",
                count=len(stale_items),
                mr_iids=[item.mr_iid for item in stale_items],
            )

        return stale_items

    async def mark_stale_warning_sent(self, mr_iid: int) -> bool:
        """Mark that stale warning has been sent for an MR.

        Args:
            mr_iid: The MR's internal ID.

        Returns:
            True if updated, False if MR not found.
        """
        log.debug("Marking stale warning sent", mr_iid=mr_iid)

        async with self.db.transaction() as session:
            cursor_result = await session.execute(
                text(_MARK_STALE_WARNING_SENT_SQL),
                {"iid": mr_iid},
            )
            changed: bool = cursor_result.rowcount > 0  # type: ignore[attr-defined]

        if changed:
            self._cache.invalidate()  # Invalidate cache after stale warning update
            log.info("Stale warning marked as sent", mr_iid=mr_iid)
        else:
            log.warning("MR not found for stale warning update", mr_iid=mr_iid)

        return changed

    def _row_to_queue_item(self, row: RowMapping | dict[str, Any]) -> QueueItem:
        """Convert a database row to a QueueItem.

        Args:
            row: Dictionary from SQLite query result.

        Returns:
            QueueItem instance.
        """
        queued_at = row["queued_at"]
        if isinstance(queued_at, str):
            queued_at = datetime.fromisoformat(queued_at)

        started_at = row.get("started_at")
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at)

        finished_at = row.get("finished_at")
        if isinstance(finished_at, str):
            finished_at = datetime.fromisoformat(finished_at)

        labels_raw = row.get("labels")
        labels: list[str]
        if labels_raw is None:
            labels = []
        elif isinstance(labels_raw, str):
            labels = json.loads(labels_raw) if labels_raw else []
        else:
            labels = labels_raw

        return QueueItem(
            mr_iid=row["iid"],
            title=row["title"],
            author_name=row["author_name"],
            author_username=row["author_username"],
            target_branch=row["target_branch"],
            state=row["status"],
            queued_at=queued_at,
            is_hotfix=bool(row.get("is_hotfix", 0)),
            author_avatar=row.get("author_avatar"),
            labels=labels,
            started_at=started_at,
            finished_at=finished_at,
            pipeline_id=row.get("pipeline_id"),
            pipeline_status=row.get("pipeline_status"),
            retry_count=row.get("retry_count", 0),
            last_error=row.get("last_error"),
            stale_warning_sent=bool(row.get("stale_warning_sent", 0)),
        )


__all__: list[str] = [
    "QueueError",
    "QueueItemNotFoundError",
    "QueueManager",
]
