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
from sqlalchemy.exc import IntegrityError

from gitlab_queue.metrics import OPERATIONS_TOTAL
from gitlab_queue.models.queue_item import DashboardStats, QueueItem
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy import RowMapping

    from gitlab_queue.db.database import Database
    from gitlab_queue.models.mr import MergeRequest

log = get_logger(__name__)

_ALLOWED_UPDATE_FIELDS = frozenset(
    {
        "pipeline_id",
        "pipeline_status",
        "last_error",
        "retry_count",
        "expected_sha",
        "retried_jobs",
    }
)
_JSON_SERIALIZED_FIELDS = frozenset({"retried_jobs"})


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
    expected_sha TEXT,
    retry_count INTEGER DEFAULT 0,
    retried_jobs TEXT DEFAULT '{}',
    last_error TEXT,
    stale_warning_sent INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_HISTORY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS merge_requests_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    iid INTEGER NOT NULL,
    title TEXT NOT NULL,
    author_name TEXT NOT NULL,
    author_username TEXT NOT NULL,
    author_avatar TEXT,
    status TEXT NOT NULL,
    is_hotfix INTEGER DEFAULT 0 NOT NULL,
    labels TEXT,
    target_branch TEXT NOT NULL,
    queued_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT NOT NULL,
    wait_time_seconds INTEGER,
    processing_time_seconds INTEGER,
    failure_reason TEXT,
    pipeline_id INTEGER,
    pipeline_status TEXT,
    pipeline_duration_seconds INTEGER,
    pipeline_failed_jobs TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_mr_status ON merge_requests(status)",
    "CREATE INDEX IF NOT EXISTS idx_mr_queued_at ON merge_requests(queued_at)",
    "CREATE INDEX IF NOT EXISTS idx_mr_iid ON merge_requests(iid)",
    "CREATE INDEX IF NOT EXISTS idx_mr_finished_at ON merge_requests(finished_at)",
]

_CREATE_HISTORY_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_history_finished_at ON merge_requests_history(finished_at)",
    "CREATE INDEX IF NOT EXISTS idx_history_status ON merge_requests_history(status)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_history_iid_unique ON merge_requests_history(iid)",
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
ORDER BY is_hotfix DESC, id ASC
"""

_SELECT_NEXT_MR_SQL = """
SELECT * FROM merge_requests
WHERE status = 'queued'
ORDER BY is_hotfix DESC, id ASC
LIMIT 1
"""

_UPDATE_STATUS_SQL = """
UPDATE merge_requests
SET status = :status
WHERE iid = :iid AND status != :status
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

_SELECT_RECENT_HISTORY_SQL = """
SELECT * FROM merge_requests_history
WHERE status IN ('merged', 'failed', 'removed', 'conflict', 'timeout')
AND finished_at IS NOT NULL
ORDER BY finished_at DESC
LIMIT :limit
"""

_SELECT_STATS_WINDOW_SQL = """
SELECT
    SUM(CASE WHEN status = 'merged' THEN 1 ELSE 0 END) as merged_count,
    SUM(CASE WHEN status IN ('merged', 'failed', 'conflict', 'timeout') THEN 1 ELSE 0 END) as total_completed,
    AVG(CASE WHEN started_at IS NOT NULL AND queued_at IS NOT NULL THEN
        (julianday(started_at) - julianday(queued_at)) * 86400 ELSE NULL END
    ) as avg_wait_seconds,
    AVG(CASE WHEN finished_at IS NOT NULL AND started_at IS NOT NULL AND status = 'merged' THEN
        (julianday(finished_at) - julianday(started_at)) * 86400 ELSE NULL END
    ) as avg_processing_seconds
FROM merge_requests_history
WHERE finished_at >= datetime('now', :days_param)
"""

_INSERT_HISTORY_SQL = """
INSERT INTO merge_requests_history (
    iid, title, author_name, author_username, author_avatar,
    status, is_hotfix, labels, target_branch,
    queued_at, started_at, finished_at,
    wait_time_seconds, processing_time_seconds, failure_reason,
    pipeline_id, pipeline_status, pipeline_duration_seconds, pipeline_failed_jobs
)
VALUES (
    :iid, :title, :author_name, :author_username, :author_avatar,
    :status, :is_hotfix, :labels, :target_branch,
    :queued_at, :started_at, :finished_at,
    :wait_time_seconds, :processing_time_seconds, :failure_reason,
    :pipeline_id, :pipeline_status, :pipeline_duration_seconds, :pipeline_failed_jobs
)
"""

_DELETE_MR_SQL = """
DELETE FROM merge_requests WHERE iid = :iid
"""

_UPDATE_HOTFIX_STATUS_SQL = """
UPDATE merge_requests
SET is_hotfix = :is_hotfix, labels = :labels
WHERE iid = :iid
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
        _version: Monotonic version counter incremented on invalidation.
    """

    _active_queue: list[QueueItem] | None = field(default=None)
    _last_refresh: datetime | None = field(default=None)
    _version: int = field(default=0)

    def invalidate(self) -> None:
        """Clear all cached data."""
        self._active_queue = None
        self._last_refresh = None
        self._version += 1

    @property
    def version(self) -> int:
        """Get current cache version for stale-write protection."""
        return self._version

    @property
    def is_valid(self) -> bool:
        """Check if cache contains valid data."""
        return self._active_queue is not None

    def get_active_queue(self) -> list[QueueItem] | None:
        """Get cached active queue or None if cache is invalid."""
        return self._active_queue

    def set_active_queue(self, items: list[QueueItem], *, version: int | None = None) -> None:
        """Update cached active queue.

        Args:
            items: Active queue items to cache.
            version: Optional version captured before an async refresh. If provided and
                differs from current cache version, the write is skipped to avoid
                overwriting newer data with stale results.
        """
        if version is not None and version != self._version:
            return
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
        """Create the merge_requests and history tables if they don't exist.

        Safe to call multiple times - uses CREATE IF NOT EXISTS.
        Also handles schema migrations for new columns.
        """
        log.debug("Ensuring database schema exists")

        async with self.db.transaction() as session:
            # Create active queue table
            await session.execute(text(_CREATE_TABLE_SQL))
            for index_sql in _CREATE_INDEXES_SQL:
                await session.execute(text(index_sql))

            # Create history table
            await session.execute(text(_CREATE_HISTORY_TABLE_SQL))
            for index_sql in _CREATE_HISTORY_INDEXES_SQL:
                await session.execute(text(index_sql))

        log.info("Database schema ensured")

    async def add_to_queue(
        self,
        mr: MergeRequest,
        is_hotfix: bool = False,
    ) -> QueueItem:
        """Add a merge request to the queue.

        Idempotent - if the MR is already in active queue, returns the existing item.
        If MR exists in terminal state (failed/merged/removed), it will be deleted
        and re-added as 'queued'.

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

        terminal_states = ("merged", "failed", "removed")

        async with self.db.transaction() as session:
            # Check if MR already exists
            result = await session.execute(
                text(_SELECT_MR_BY_IID_SQL),
                {"iid": mr.iid},
            )
            existing = result.mappings().one_or_none()

            # If exists in terminal state, delete it first (should have been in history)
            if existing and existing["status"] in terminal_states:
                log.info(
                    "Removing stale terminal-state MR before re-adding",
                    mr_iid=mr.iid,
                    old_status=existing["status"],
                )
                await session.execute(
                    text(_DELETE_MR_SQL),
                    {"iid": mr.iid},
                )
                existing = None

            # Insert new MR (or skip if already in active state)
            if existing is None:
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

        # If cache is invalidated during refresh, avoid returning stale results.
        # We'll retry once if we detect version churn and cache remains empty.
        for _ in range(2):
            version_before = self._cache.version

            # Fetch from database and attempt to cache
            async with self.db.session() as session:
                result = await session.execute(text(_SELECT_ACTIVE_QUEUE_SQL))
                rows = result.mappings().all()
                await session.commit()

            items = [self._row_to_queue_item(row) for row in rows]
            self._cache.set_active_queue(items, version=version_before)

            cached_after = self._cache.get_active_queue()
            if cached_after is not None:
                return cached_after

            # Cache still empty means version changed mid-refresh and someone invalidated it.
            # Loop and re-fetch once to align with current version.

        # Best effort fallback: return latest fetched items.
        return items

    async def get_queue_length(self) -> int:
        """Get the number of MRs in the active queue.

        Returns:
            Number of MRs with active status.
        """
        items = await self.get_active_queue()
        return len(items)

    async def get_mr_state(self, mr_iid: int) -> dict[str, Any] | None:
        """Get the current state of an MR in the queue or history.

        First checks the active queue, then falls back to history if not found.

        Args:
            mr_iid: The MR's internal ID.

        Returns:
            Dict with status, started_at, last_error, finished_at or None if not found.
        """
        async with self.db.session() as session:
            # First check active queue
            result = await session.execute(
                text(_SELECT_MR_STATE_SQL),
                {"iid": mr_iid},
            )
            row = result.mappings().one_or_none()

            # If not found in active queue, check history
            if row is None:
                result = await session.execute(
                    text(
                        "SELECT status, started_at, failure_reason as last_error, "
                        "finished_at FROM merge_requests_history WHERE iid = :iid "
                        "ORDER BY id DESC LIMIT 1"
                    ),
                    {"iid": mr_iid},
                )
                row = result.mappings().one_or_none()

            await session.commit()

        if row is None:
            return None

        return {
            "status": row["status"],
            "started_at": (datetime.fromisoformat(row["started_at"]) if row["started_at"] else None),
            "last_error": row["last_error"],
            "finished_at": (datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None),
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
        set_clauses.append(
            "started_at = CASE "
            "WHEN started_at IS NULL AND status = 'queued' AND :status != 'queued' "
            "THEN :started_at ELSE started_at END"
        )
        params["started_at"] = now.isoformat()

        # Auto-set finished_at for terminal states
        if state in terminal_states:
            set_clauses.append("finished_at = COALESCE(finished_at, :finished_at)")
            params["finished_at"] = now.isoformat()

        # Handle extra fields
        for field_name, value in extra.items():
            if field_name not in _ALLOWED_UPDATE_FIELDS:
                continue
            if field_name in _JSON_SERIALIZED_FIELDS and isinstance(value, dict):
                value = json.dumps(value)
            set_clauses.append(f"{field_name} = :{field_name}")
            params[field_name] = value

        # Auto-derive retry_count from retried_jobs (single source of truth)
        if "retried_jobs" in extra and "retry_count" not in params:
            rj = extra["retried_jobs"]
            if isinstance(rj, dict) and rj:
                set_clauses.append("retry_count = :retry_count")
                params["retry_count"] = max(rj.values())

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

    async def update_hotfix_status(
        self,
        mr_iid: int,
        is_hotfix: bool,
        labels: list[str],
    ) -> bool:
        """Update the hotfix status and labels of an MR in the queue.

        This is used when the hotfix label is added or removed from an MR
        that is already in the queue.

        Args:
            mr_iid: The MR's internal ID.
            is_hotfix: New hotfix status.
            labels: Current labels on the MR.

        Returns:
            True if updated, False if MR not found.
        """
        log.debug(
            "Updating MR hotfix status",
            mr_iid=mr_iid,
            is_hotfix=is_hotfix,
            labels=labels,
        )

        labels_json = json.dumps(labels)

        async with self.db.transaction() as session:
            params = {
                "iid": mr_iid,
                "is_hotfix": 1 if is_hotfix else 0,
                "labels": labels_json,
            }
            cursor_result = await session.execute(text(_UPDATE_HOTFIX_STATUS_SQL), params)
            changed: bool = cursor_result.rowcount > 0  # type: ignore[attr-defined]

        if changed:
            self._cache.invalidate()
            OPERATIONS_TOTAL.labels(type="update", status="success").inc()
            log.info(
                "MR hotfix status updated",
                mr_iid=mr_iid,
                is_hotfix=is_hotfix,
            )
        else:
            log.debug("MR not found for hotfix status update", mr_iid=mr_iid)

        return changed

    async def complete_mr(
        self,
        mr_iid: int,
        status: str,
        failure_reason: str | None = None,
        pipeline_duration_seconds: int | None = None,
        pipeline_failed_jobs: list[str] | None = None,
    ) -> bool:
        """Move MR from active queue to history table.

        This is an atomic operation that:
        1. Reads the MR from active queue
        2. Creates history record with computed timing fields
        3. Deletes from active queue

        Should be called after MR reaches terminal state (merged, failed, removed).

        Args:
            mr_iid: MR internal ID.
            status: Final status (merged, failed, conflict, timeout, removed).
            failure_reason: Reason for failure if applicable.
            pipeline_duration_seconds: Total pipeline duration.
            pipeline_failed_jobs: List of failed job names.

        Returns:
            True if MR was moved to history, False if not found.
        """
        log.debug(
            "Completing MR and moving to history",
            mr_iid=mr_iid,
            status=status,
            failure_reason=failure_reason,
        )

        # First get the MR data
        mr = await self.get_queue_item(mr_iid)
        if not mr:
            log.debug(
                "MR not found for completion (already completed)",
                mr_iid=mr_iid,
                status=status,
            )
            # Invalidate cache in case it contains stale data for this MR
            self._cache.invalidate()
            return False

        now = datetime.now(UTC)
        finished_at = now.isoformat()

        wait_time_seconds, processing_time_seconds = self._compute_timing(mr, now)

        # Prepare history record params
        history_params = {
            "iid": mr.mr_iid,
            "title": mr.title,
            "author_name": mr.author_name,
            "author_username": mr.author_username,
            "author_avatar": mr.author_avatar,
            "status": status,
            "is_hotfix": 1 if mr.is_hotfix else 0,
            "labels": json.dumps(mr.labels) if mr.labels else None,
            "target_branch": mr.target_branch,
            "queued_at": mr.queued_at.isoformat() if mr.queued_at else finished_at,
            "started_at": mr.started_at.isoformat() if mr.started_at else None,
            "finished_at": finished_at,
            "wait_time_seconds": wait_time_seconds,
            "processing_time_seconds": processing_time_seconds,
            "failure_reason": failure_reason,
            "pipeline_id": mr.pipeline_id,
            "pipeline_status": mr.pipeline_status,
            "pipeline_duration_seconds": pipeline_duration_seconds,
            "pipeline_failed_jobs": json.dumps(pipeline_failed_jobs) if pipeline_failed_jobs else None,
        }

        try:
            async with self.db.transaction() as session:
                # Insert into history
                await session.execute(text(_INSERT_HISTORY_SQL), history_params)
                # Delete from active queue
                await session.execute(text(_DELETE_MR_SQL), {"iid": mr_iid})
        except IntegrityError as e:
            # Only suppress the expected duplicate-key race condition on history table
            error_msg = str(e).lower()
            is_history_duplicate = "merge_requests_history" in error_msg and (
                "unique constraint" in error_msg or "duplicate" in error_msg
            )
            if not is_history_duplicate:
                # Unexpected integrity error - re-raise to avoid hiding real issues
                raise

            log.debug(
                "MR completion race: already in history",
                mr_iid=mr_iid,
                status=status,
            )
            # Explicitly delete from active table in a separate transaction
            async with self.db.transaction() as session:
                await session.execute(text(_DELETE_MR_SQL), {"iid": mr_iid})
            self._cache.invalidate()
            return False

        self._cache.invalidate()
        OPERATIONS_TOTAL.labels(type="complete", status="success").inc()
        log.info(
            "MR completed and moved to history",
            mr_iid=mr_iid,
            status=status,
            wait_time_seconds=wait_time_seconds,
            processing_time_seconds=processing_time_seconds,
        )
        return True

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

    @staticmethod
    def _ensure_utc(dt: datetime | None) -> datetime | None:
        """Normalize a possibly naive datetime to UTC-aware."""
        if dt is not None and dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

    @staticmethod
    def _compute_timing(mr: QueueItem, now: datetime) -> tuple[int | None, int | None]:
        """Compute wait and processing time for a completed MR.

        Args:
            mr: Queue item with timing info.
            now: Current UTC timestamp.

        Returns:
            Tuple of (wait_time_seconds, processing_time_seconds).
        """
        queued_at = QueueManager._ensure_utc(mr.queued_at)
        started_at = QueueManager._ensure_utc(mr.started_at)

        if queued_at and started_at:
            return (
                int((started_at - queued_at).total_seconds()),
                int((now - started_at).total_seconds()),
            )
        if queued_at:
            return int((now - queued_at).total_seconds()), None
        return None, None

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
            if not labels_raw:
                labels = []
            else:
                try:
                    labels = json.loads(labels_raw)
                except json.JSONDecodeError:
                    log.warning(
                        "Invalid JSON in labels column, using empty list",
                        mr_iid=row.get("iid"),
                    )
                    labels = []
        else:
            labels = labels_raw

        retried_jobs_raw = row.get("retried_jobs")
        retried_jobs: dict[str, int]
        if not retried_jobs_raw:
            retried_jobs = {}
        else:
            try:
                parsed = json.loads(retried_jobs_raw)
                retried_jobs = parsed if isinstance(parsed, dict) else {}
            except (json.JSONDecodeError, TypeError):
                retried_jobs = {}

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
            expected_sha=row.get("expected_sha"),
            retry_count=row.get("retry_count", 0),
            retried_jobs=retried_jobs,
            last_error=row.get("last_error"),
            stale_warning_sent=bool(row.get("stale_warning_sent", 0)),
        )


__all__: list[str] = [
    "QueueError",
    "QueueItemNotFoundError",
    "QueueManager",
]
