"""Queue Manager for GitLab Merge Queue Bot.

Manages the merge request queue with SQLite storage, providing
FIFO ordering with hotfix priority support.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from gitlab_queue.models.queue_item import QueueItem
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
# Queue Manager
# =============================================================================


@dataclass
class QueueManager:
    """Manages the merge request queue in SQLite.

    Provides FIFO ordering with hotfix priority support. All operations
    are idempotent and transaction-safe.

    Attributes:
        db: Database instance for SQLite operations.

    Example:
        >>> from gitlab_queue.db.database import Database
        >>> async with Database("sqlite+aiosqlite:///data/queue.db") as db:
        ...     queue = QueueManager(db)
        ...     await queue.ensure_schema()
        ...     await queue.add_to_queue(mr, is_hotfix=False)
    """

    db: Database

    async def ensure_schema(self) -> None:
        """Create the merge_requests table and indexes if they don't exist.

        Safe to call multiple times - uses CREATE IF NOT EXISTS.
        """
        log.debug("Ensuring database schema exists")

        async with self.db.transaction() as session:
            await session.execute(text(_CREATE_TABLE_SQL))
            for index_sql in _CREATE_INDEXES_SQL:
                await session.execute(text(index_sql))

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
            log.info("MR removed from queue", mr_iid=mr_iid)
        else:
            log.debug("MR not removed (already removed or not found)", mr_iid=mr_iid)

        return changed

    async def get_queue_position(self, mr_iid: int) -> int | None:
        """Get the position of an MR in the active queue.

        Position is 1-indexed (first MR in queue = position 1).
        Considers hotfix priority in ordering.

        Args:
            mr_iid: The MR's internal ID.

        Returns:
            Position (1-indexed) if in active queue, None if not found or removed.
        """
        async with self.db.session() as session:
            # First check if MR exists and is in active state
            result = await session.execute(
                text(_SELECT_MR_BY_IID_SQL),
                {"iid": mr_iid},
            )
            row = result.mappings().one_or_none()

            if row is None:
                return None

            # Check if in active state
            status = row["status"]
            if status not in ("queued", "rebasing", "testing", "merging"):
                return None

            # Count items ahead of this one
            result = await session.execute(
                text(_COUNT_POSITION_SQL),
                {"iid": mr_iid},
            )
            count = result.scalar() or 0
            await session.commit()

        return count + 1  # 1-indexed

    async def get_next_mr(self) -> QueueItem | None:
        """Get the next MR to process from the queue.

        Returns the first MR with status 'queued', ordered by:
        1. is_hotfix DESC (hotfixes first)
        2. queued_at ASC (FIFO within priority)

        Returns:
            Next QueueItem to process, or None if queue is empty.
        """
        async with self.db.session() as session:
            result = await session.execute(text(_SELECT_NEXT_MR_SQL))
            row = result.mappings().one_or_none()
            await session.commit()

        if row is None:
            return None

        return self._row_to_queue_item(row)

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
        ordered by hotfix priority and queue time.

        Returns:
            List of QueueItems in queue order.
        """
        async with self.db.session() as session:
            result = await session.execute(text(_SELECT_ACTIVE_QUEUE_SQL))
            rows = result.mappings().all()
            await session.commit()

        return [self._row_to_queue_item(row) for row in rows]

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
                datetime.fromisoformat(row["finished_at"])
                if row["finished_at"]
                else None
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
        for field, value in extra.items():
            if field in allowed_fields:
                set_clauses.append(f"{field} = :{field}")
                params[field] = value

        sql = f"UPDATE merge_requests SET {', '.join(set_clauses)} WHERE iid = :iid"

        async with self.db.transaction() as session:
            cursor_result = await session.execute(text(sql), params)
            changed: bool = cursor_result.rowcount > 0  # type: ignore[attr-defined]

        if changed:
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
            log.info(
                "Old queue entries cleaned up", deleted_count=deleted_count, days=days
            )
        else:
            log.debug("No old entries to clean up")

        return deleted_count

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

        labels = row.get("labels", "[]")
        if isinstance(labels, str):
            labels = json.loads(labels) if labels else []

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
        )


__all__: list[str] = [
    "QueueError",
    "QueueItemNotFoundError",
    "QueueManager",
]
