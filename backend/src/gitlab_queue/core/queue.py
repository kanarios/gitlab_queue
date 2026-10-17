"""Queue Manager for GitLab Merge Queue Bot.

Manages the merge request queue with SQLite storage, providing
FIFO ordering with hotfix priority support.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import text

from gitlab_queue.metrics import OPERATIONS_TOTAL
from gitlab_queue.models.completion import CompletionRequest, requeue_is_cancelled
from gitlab_queue.models.queue_item import DashboardStats, QueueItem
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from asyncio import Lock

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
        "processing_attempts",
    }
)
_JSON_SERIALIZED_FIELDS = frozenset({"retried_jobs"})


# =============================================================================
# SQL Statements
# =============================================================================

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS merge_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL DEFAULT 0,
    iid INTEGER NOT NULL,
    title TEXT NOT NULL,
    author_name TEXT NOT NULL,
    author_username TEXT NOT NULL,
    author_avatar TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    is_hotfix INTEGER DEFAULT 0,
    labels TEXT,
    metadata_version INTEGER NOT NULL DEFAULT 0,
    pending_notification TEXT,
    pending_completion TEXT,
    requeue_request TEXT,
    ignored_label_events TEXT,
    target_branch TEXT NOT NULL,
    queued_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    pipeline_id INTEGER,
    pipeline_status TEXT,
    expected_sha TEXT,
    retry_count INTEGER DEFAULT 0,
    retried_jobs TEXT NOT NULL DEFAULT '{}',
    last_error TEXT,
    stale_warning_sent INTEGER DEFAULT 0,
    processing_attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, iid)
)
"""

_CREATE_HISTORY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS merge_requests_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL DEFAULT 0,
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
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, iid)
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
]

_INSERT_MR_SQL = """
INSERT INTO merge_requests (
    project_id, iid, title, author_name, author_username, author_avatar,
    status, is_hotfix, labels, target_branch, queued_at
)
VALUES (
    :project_id, :iid, :title, :author_name, :author_username, :author_avatar,
    'queued', :is_hotfix, :labels, :target_branch, :queued_at
)
ON CONFLICT(project_id, iid) DO NOTHING
"""

_SELECT_MR_BY_IID_SQL = """
SELECT * FROM merge_requests WHERE iid = :iid AND project_id = :project_id
"""

_SELECT_ACTIVE_QUEUE_BASE_SQL = """
SELECT * FROM merge_requests
WHERE status IN ('queued', 'rebasing', 'testing', 'merging')
"""

_SELECT_ACTIVE_QUEUE_PROJECT_SQL = (
    _SELECT_ACTIVE_QUEUE_BASE_SQL
    + """AND project_id = :project_id
"""
)

_SELECT_ACTIVE_QUEUE_ORDER_SQL = """ORDER BY is_hotfix DESC, id ASC
"""

_SELECT_NEXT_MR_SQL = """
SELECT * FROM merge_requests
WHERE status = 'queued' AND project_id = :project_id
ORDER BY is_hotfix DESC, id ASC
LIMIT 1
"""

_UPDATE_STATUS_SQL = """
UPDATE merge_requests
SET status = :status
WHERE iid = :iid AND project_id = :project_id AND status != :status
"""

_SELECT_MR_STATE_SQL = """
SELECT status, started_at, last_error, finished_at FROM merge_requests WHERE iid = :iid AND project_id = :project_id
"""

_SELECT_QUEUE_STATS_BASE_SQL = """
SELECT status, COUNT(*) as count FROM merge_requests
WHERE status IN ('queued', 'rebasing', 'testing', 'merging')
"""

_SELECT_QUEUE_STATS_PROJECT_SQL = """AND project_id = :project_id
"""

_SELECT_QUEUE_STATS_GROUP_SQL = """GROUP BY status
"""

_CLEANUP_OLD_ENTRIES_SQL = """
DELETE FROM merge_requests
WHERE finished_at IS NOT NULL AND finished_at < datetime('now', :days_param) AND project_id = :project_id
"""

_SELECT_STALE_MRS_SQL = """
SELECT * FROM merge_requests
WHERE status IN ('queued', 'rebasing', 'testing', 'merging')
AND stale_warning_sent = 0
AND queued_at < datetime('now', :hours_param)
AND project_id = :project_id
ORDER BY queued_at ASC
"""

_MARK_STALE_WARNING_SENT_SQL = """
UPDATE merge_requests
SET stale_warning_sent = 1
WHERE iid = :iid AND project_id = :project_id
"""

_SELECT_RECENT_HISTORY_BASE_SQL = """
SELECT * FROM merge_requests_history
WHERE status IN ('merged', 'failed', 'removed', 'conflict', 'timeout')
AND finished_at IS NOT NULL
"""

_SELECT_RECENT_HISTORY_PROJECT_SQL = """AND project_id = :project_id
"""

_SELECT_RECENT_HISTORY_TAIL_SQL = """ORDER BY finished_at DESC
LIMIT :limit
"""

_SELECT_STATS_WINDOW_BASE_SQL = """
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

_SELECT_STATS_WINDOW_PROJECT_SQL = """AND project_id = :project_id
"""

_INSERT_HISTORY_SQL = """
INSERT INTO merge_requests_history (
    project_id, iid, title, author_name, author_username, author_avatar,
    status, is_hotfix, labels, target_branch,
    queued_at, started_at, finished_at,
    wait_time_seconds, processing_time_seconds, failure_reason,
    pipeline_id, pipeline_status, pipeline_duration_seconds, pipeline_failed_jobs
)
VALUES (
    :project_id, :iid, :title, :author_name, :author_username, :author_avatar,
    :status, :is_hotfix, :labels, :target_branch,
    :queued_at, :started_at, :finished_at,
    :wait_time_seconds, :processing_time_seconds, :failure_reason,
    :pipeline_id, :pipeline_status, :pipeline_duration_seconds, :pipeline_failed_jobs
)
"""

_DELETE_MR_SQL = """
DELETE FROM merge_requests WHERE iid = :iid AND project_id = :project_id
"""

_UPDATE_HOTFIX_STATUS_SQL = """
UPDATE merge_requests
SET is_hotfix = :is_hotfix, labels = :labels, metadata_version = metadata_version + 1
WHERE iid = :iid AND project_id = :project_id
  AND status IN ('queued', 'rebasing', 'testing', 'merging')
  AND (:expected_id IS NULL OR (id = :expected_id AND metadata_version = :expected_version))
  AND (is_hotfix != :is_hotfix OR COALESCE(labels, '[]') != :labels)
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

    def metadata_lock(self, project_id: int) -> Lock:
        """Serialize metadata changes and their feedback across all entrypoints."""
        return self.db.queue_metadata_lock(project_id)

    def notification_lock(self, project_id: int, mr_iid: int) -> Lock:
        return self.db.queue_notification_lock(project_id, mr_iid)

    def completion_lock(self, project_id: int, mr_iid: int) -> Lock:
        return self.db.queue_completion_lock(project_id, mr_iid)

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
        project_id: int,
        mr: MergeRequest,
        is_hotfix: bool = False,
    ) -> QueueItem:
        """Add a merge request to the queue.

        Idempotent - if the MR is already in active queue, returns the existing item.
        If MR exists in terminal state (failed/merged/removed), it will be deleted
        and re-added as 'queued'.

        Args:
            project_id: The GitLab project ID.
            mr: The MergeRequest to add.
            is_hotfix: Whether this MR has hotfix priority.

        Returns:
            QueueItem representing the MR in the queue.
        """
        now = datetime.now(UTC)
        labels_json = json.dumps(mr.labels)

        log.debug(
            "Adding MR to queue",
            project_id=project_id,
            mr_iid=mr.iid,
            is_hotfix=is_hotfix,
            title=mr.title,
        )

        terminal_states = ("merged", "failed", "removed")

        async with self.db.transaction() as session:
            # Check if MR already exists
            result = await session.execute(
                text(_SELECT_MR_BY_IID_SQL),
                {"iid": mr.iid, "project_id": project_id},
            )
            existing = result.mappings().one_or_none()

            # If exists in terminal state, delete it first (should have been in history)
            if existing and existing["status"] in terminal_states and existing["pending_completion"] is None:
                log.info(
                    "Removing stale terminal-state MR before re-adding",
                    mr_iid=mr.iid,
                    old_status=existing["status"],
                )
                await session.execute(
                    text(_DELETE_MR_SQL),
                    {"iid": mr.iid, "project_id": project_id},
                )
                existing = None

            # Insert new MR (or skip if already in active state)
            if existing is None:
                await session.execute(
                    text(_INSERT_MR_SQL),
                    {
                        "project_id": project_id,
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
                {"iid": mr.iid, "project_id": project_id},
            )
            row = result.mappings().one()

        item = self._row_to_queue_item(row)
        self._cache.invalidate()  # Invalidate cache after queue modification
        OPERATIONS_TOTAL.labels(project_id=str(project_id), type="add", status="success").inc()
        log.info(
            "MR added to queue",
            mr_iid=mr.iid,
            state=item.state,
            is_hotfix=item.is_hotfix,
        )
        return item

    async def remove_from_queue(self, project_id: int, mr_iid: int) -> bool:
        """Remove a merge request from the queue by setting status to 'removed'.

        Idempotent - returns True if status was changed, False if already removed
        or not found.

        Args:
            project_id: The GitLab project ID.
            mr_iid: The MR's internal ID.

        Returns:
            True if the MR was removed, False if already removed or not found.
        """
        log.debug("Removing MR from queue", project_id=project_id, mr_iid=mr_iid)

        async with self.db.transaction() as session:
            cursor_result = await session.execute(
                text(_UPDATE_STATUS_SQL),
                {"iid": mr_iid, "project_id": project_id, "status": "removed"},
            )
            # CursorResult has rowcount for DML statements
            changed: bool = cursor_result.rowcount > 0  # type: ignore[attr-defined]

        if changed:
            self._cache.invalidate()  # Invalidate cache after queue modification
            OPERATIONS_TOTAL.labels(project_id=str(project_id), type="remove", status="success").inc()
            log.info("MR removed from queue", mr_iid=mr_iid)
        else:
            log.debug("MR not removed (already removed or not found)", mr_iid=mr_iid)

        return changed

    async def get_queue_position(self, project_id: int, mr_iid: int) -> int | None:
        """Get the position of an MR in the active queue.

        Position is 1-indexed (first MR in queue = position 1).
        Considers hotfix priority in ordering. Uses in-memory cache
        via get_active_queue().

        Args:
            project_id: The GitLab project ID.
            mr_iid: The MR's internal ID.

        Returns:
            Position (1-indexed) if in active queue, None if not found or removed.
        """
        queue = await self.get_active_queue(project_id)
        for i, item in enumerate(queue):
            if item.mr_iid == mr_iid:
                return i + 1  # 1-indexed
        return None

    async def get_next_mr(self, project_id: int) -> QueueItem | None:
        """Get the next MR to process from the queue.

        Returns the first MR with status 'queued', ordered by:
        1. is_hotfix DESC (hotfixes first)
        2. queued_at ASC (FIFO within priority)

        Uses in-memory cache via get_active_queue().

        Args:
            project_id: The GitLab project ID.

        Returns:
            Next QueueItem to process, or None if queue is empty.
        """
        queue = await self.get_active_queue(project_id)
        for item in queue:
            if item.state == "queued":
                return item
        return None

    async def get_queue_item(self, project_id: int, mr_iid: int) -> QueueItem | None:
        """Get a queue item by MR IID.

        Args:
            project_id: The GitLab project ID.
            mr_iid: The MR's internal ID.

        Returns:
            QueueItem if found, None otherwise.
        """
        async with self.db.session() as session:
            result = await session.execute(
                text(_SELECT_MR_BY_IID_SQL),
                {"iid": mr_iid, "project_id": project_id},
            )
            row = result.mappings().one_or_none()
            await session.commit()

        if row is None:
            return None

        return self._row_to_queue_item(row)

    async def get_active_queue(self, project_id: int | None = None) -> list[QueueItem]:
        """Get all MRs in the active queue.

        Returns MRs with status in ('queued', 'rebasing', 'testing', 'merging'),
        ordered by hotfix priority and queue time. Uses in-memory cache when available
        (only for unfiltered queries).

        Args:
            project_id: Filter by project ID. None returns all projects.

        Returns:
            List of QueueItems in queue order.
        """
        # Return cached data if available (only for unfiltered queries)
        if project_id is None:
            cached = self._cache.get_active_queue()
            if cached is not None:
                return cached

        # Build SQL based on project_id filter
        if project_id is not None:
            sql = _SELECT_ACTIVE_QUEUE_PROJECT_SQL + _SELECT_ACTIVE_QUEUE_ORDER_SQL
            params: dict[str, Any] = {"project_id": project_id}
        else:
            sql = _SELECT_ACTIVE_QUEUE_BASE_SQL + _SELECT_ACTIVE_QUEUE_ORDER_SQL
            params = {}

        # If cache is invalidated during refresh, avoid returning stale results.
        # We'll retry once if we detect version churn and cache remains empty.
        for _ in range(2):
            version_before = self._cache.version

            # Fetch from database and attempt to cache
            async with self.db.session() as session:
                result = await session.execute(text(sql), params)
                rows = result.mappings().all()
                await session.commit()

            items = [self._row_to_queue_item(row) for row in rows]

            # Only cache unfiltered results
            if project_id is None:
                self._cache.set_active_queue(items, version=version_before)

                cached_after = self._cache.get_active_queue()
                if cached_after is not None:
                    return cached_after
            else:
                return items

            # Cache still empty means version changed mid-refresh and someone invalidated it.
            # Loop and re-fetch once to align with current version.

        # Best effort fallback: return latest fetched items.
        return items

    async def get_queue_length(self, project_id: int | None = None) -> int:
        """Get the number of MRs in the active queue.

        Args:
            project_id: Filter by project ID. None returns count for all projects.

        Returns:
            Number of MRs with active status.
        """
        items = await self.get_active_queue(project_id)
        return len(items)

    async def get_mr_state(self, project_id: int, mr_iid: int) -> dict[str, Any] | None:
        """Get the current state of an MR in the queue or history.

        First checks the active queue, then falls back to history if not found.

        Args:
            project_id: The GitLab project ID.
            mr_iid: The MR's internal ID.

        Returns:
            Dict with status, started_at, last_error, finished_at or None if not found.
        """
        async with self.db.session() as session:
            # First check active queue
            result = await session.execute(
                text(_SELECT_MR_STATE_SQL),
                {"iid": mr_iid, "project_id": project_id},
            )
            row = result.mappings().one_or_none()

            # If not found in active queue, check history
            if row is None:
                result = await session.execute(
                    text(
                        "SELECT status, started_at, failure_reason as last_error, "
                        "finished_at FROM merge_requests_history "
                        "WHERE iid = :iid AND project_id = :project_id "
                        "ORDER BY id DESC LIMIT 1"
                    ),
                    {"iid": mr_iid, "project_id": project_id},
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
        project_id: int,
        mr_iid: int,
        state: str,
        **extra: Any,
    ) -> bool:
        """Update the state of an MR in the queue.

        Sets started_at automatically when a queued MR begins processing.
        Sets finished_at automatically for terminal states (merged, failed, removed).

        Args:
            project_id: The GitLab project ID.
            mr_iid: The MR's internal ID.
            state: New state to set.
            **extra: Additional fields to update (pipeline_id, pipeline_status,
                last_error, retry_count).

        Returns:
            True if updated.

        Raises:
            QueueItemNotFoundError: If MR not in queue.
        """
        log.debug("Updating MR state", project_id=project_id, mr_iid=mr_iid, new_state=state, extra=extra)

        now = datetime.now(UTC)
        terminal_states = ("merged", "failed", "removed")

        # Build dynamic UPDATE query
        set_clauses = ["status = :status"]
        params: dict[str, Any] = {"iid": mr_iid, "project_id": project_id, "status": state}

        # Auto-set started_at if transitioning from queued
        set_clauses.append(
            "started_at = CASE "
            "WHEN started_at IS NULL AND status = 'queued' AND :status IN ('rebasing', 'testing', 'merging') "
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
            if isinstance(rj, dict):
                set_clauses.append("retry_count = :retry_count")
                params["retry_count"] = max(rj.values()) if rj else 0

        sql = f"UPDATE merge_requests SET {', '.join(set_clauses)} WHERE iid = :iid AND project_id = :project_id AND pending_completion IS NULL"

        async with self.db.transaction() as session:
            cursor_result = await session.execute(text(sql), params)
            changed: bool = cursor_result.rowcount > 0  # type: ignore[attr-defined]

        if changed:
            self._cache.invalidate()  # Invalidate cache after state change
            OPERATIONS_TOTAL.labels(project_id=str(project_id), type="update", status="success").inc()
            log.info("MR state updated", mr_iid=mr_iid, new_state=state)
        else:
            log.warning("MR not found for state update", mr_iid=mr_iid)
            raise QueueItemNotFoundError(mr_iid)

        return changed

    async def update_hotfix_status(
        self,
        project_id: int,
        mr_iid: int,
        is_hotfix: bool,
        labels: list[str],
        *,
        expected_revision: tuple[int, int] | None = None,
        notify_positions: bool = False,
    ) -> bool:
        """Update the hotfix status and labels of an MR in the queue.

        This is used when the hotfix label is added or removed from an MR
        that is already in the queue.

        Args:
            project_id: The GitLab project ID.
            mr_iid: The MR's internal ID.
            is_hotfix: New hotfix status.
            labels: Current labels on the MR.
            expected_revision: Optional (row identity, metadata version) to compare atomically.
            notify_positions: Persist feedback for the changed and displaced waiting MRs.

        Returns:
            True for the owner of an effective change; False for stale, duplicate or absent entries.
        """
        log.debug(
            "Updating MR hotfix status",
            project_id=project_id,
            mr_iid=mr_iid,
            is_hotfix=is_hotfix,
            labels=labels,
        )

        labels_json = json.dumps(labels)

        async with self.db.transaction() as session:
            before: dict[int, int] = {}
            if notify_positions:
                rows = await session.execute(
                    text(_SELECT_ACTIVE_QUEUE_PROJECT_SQL + _SELECT_ACTIVE_QUEUE_ORDER_SQL),
                    {"project_id": project_id},
                )
                before = {row["iid"]: pos for pos, row in enumerate(rows.mappings(), 1) if row["status"] == "queued"}
            params = {
                "iid": mr_iid,
                "project_id": project_id,
                "is_hotfix": 1 if is_hotfix else 0,
                "labels": labels_json,
                "expected_id": expected_revision[0] if expected_revision else None,
                "expected_version": expected_revision[1] if expected_revision else None,
            }
            cursor_result = await session.execute(text(_UPDATE_HOTFIX_STATUS_SQL), params)
            changed: bool = cursor_result.rowcount > 0  # type: ignore[attr-defined]
            if changed and notify_positions:
                rows = await session.execute(
                    text(_SELECT_ACTIVE_QUEUE_PROJECT_SQL + _SELECT_ACTIVE_QUEUE_ORDER_SQL),
                    {"project_id": project_id},
                )
                for pos, row in enumerate(rows.mappings(), 1):
                    old_position = before.get(row["iid"])
                    if row["status"] != "queued" or old_position is None:
                        continue
                    if row["iid"] != mr_iid and old_position == pos:
                        continue
                    pending = json.dumps(
                        {
                            "token": uuid4().hex,
                            "status": "priority_changed" if row["iid"] == mr_iid else "position_changed_priority",
                            "old_position": old_position,
                        }
                    )
                    await session.execute(
                        text("UPDATE merge_requests SET pending_notification = :pending WHERE id = :id"),
                        {"pending": pending, "id": row["id"]},
                    )

        if changed:
            self._cache.invalidate()
            OPERATIONS_TOTAL.labels(project_id=str(project_id), type="update", status="success").inc()
            log.info(
                "MR hotfix status updated",
                mr_iid=mr_iid,
                is_hotfix=is_hotfix,
            )
        else:
            log.debug("MR not found for hotfix status update", mr_iid=mr_iid)

        return changed

    async def clear_pending_notification(self, project_id: int, mr_iid: int, pending: str) -> None:
        """Acknowledge only the intent that was sent, preserving newer changes."""
        async with self.db.transaction() as session:
            await session.execute(
                text(
                    "UPDATE merge_requests SET pending_notification = NULL "
                    "WHERE project_id = :project_id AND iid = :iid AND pending_notification = :pending"
                ),
                {"project_id": project_id, "iid": mr_iid, "pending": pending},
            )
        self._cache.invalidate()

    def _history_params(self, mr: QueueItem, request: CompletionRequest, finished: datetime) -> dict[str, Any]:
        wait, processing = self._compute_timing(mr, finished)
        return {
            "project_id": mr.project_id,
            "iid": mr.mr_iid,
            "title": mr.title,
            "author_name": mr.author_name,
            "author_username": mr.author_username,
            "author_avatar": mr.author_avatar,
            "status": request.history_status,
            "is_hotfix": int(mr.is_hotfix),
            "labels": json.dumps(mr.labels) if mr.labels else None,
            "target_branch": mr.target_branch,
            "queued_at": mr.queued_at.isoformat(),
            "started_at": mr.started_at.isoformat() if mr.started_at else None,
            "finished_at": finished.isoformat(),
            "wait_time_seconds": wait,
            "processing_time_seconds": processing,
            "failure_reason": request.failure_reason,
            "pipeline_id": mr.pipeline_id,
            "pipeline_status": mr.pipeline_status,
            "pipeline_duration_seconds": request.pipeline_duration_seconds,
            "pipeline_failed_jobs": json.dumps(request.pipeline_failed_jobs) if request.pipeline_failed_jobs else None,
        }

    async def prepare_completion(self, project_id: int, mr_iid: int, request: CompletionRequest) -> QueueItem | None:
        """Freeze the original outcome before any completion HTTP request."""
        async with self.db.transaction() as session:
            result = await session.execute(text(_SELECT_MR_BY_IID_SQL), {"project_id": project_id, "iid": mr_iid})
            row = result.mappings().one_or_none()
            if row is None or (request.queue_id is not None and row["id"] != request.queue_id):
                return None
            item = self._row_to_queue_item(row)
            if item.pending_completion is not None:
                return item
            now = next(
                (
                    value
                    for key, value in request.context.items()
                    if key in ("merged_at", "failed_at", "removed_at") and isinstance(value, datetime)
                ),
                datetime.now(UTC),
            )
            payload = {
                "queue_id": item.queue_id,
                "request": asdict(request),
                "history": self._history_params(item, request, now),
                "finished_at": now.isoformat(),
                "comment_sent": False,
                "labels_removed": False,
                "label_events": [],
            }
            pending = json.dumps(payload, default=lambda value: value.isoformat())
            await session.execute(
                text(
                    "UPDATE merge_requests SET pending_completion = :pending, status = :status, "
                    "finished_at = :finished, pending_notification = NULL WHERE id = :id AND pending_completion IS NULL"
                ),
                {"pending": pending, "status": request.state, "finished": now.isoformat(), "id": item.queue_id},
            )
            item.pending_completion = pending
            item.state = request.state
            item.finished_at = now
        self._cache.invalidate()
        return item

    async def get_pending_completions(self, project_id: int) -> list[QueueItem]:
        async with self.db.session() as session:
            result = await session.execute(
                text("SELECT * FROM merge_requests WHERE project_id = :project_id AND pending_completion IS NOT NULL"),
                {"project_id": project_id},
            )
            items = [self._row_to_queue_item(row) for row in result.mappings()]
            await session.commit()
            return items

    async def save_completion_progress(self, project_id: int, queue_id: int, payload: dict[str, Any]) -> None:
        async with self.db.transaction() as session:
            await session.execute(
                text(
                    "UPDATE merge_requests SET pending_completion = :pending "
                    "WHERE project_id = :project_id AND id = :id AND pending_completion IS NOT NULL"
                ),
                {"pending": json.dumps(payload), "project_id": project_id, "id": queue_id},
            )

    async def defer_requeue(self, project_id: int, mr: MergeRequest, request: dict[str, Any]) -> None:
        params = {
            "project_id": project_id,
            "iid": mr.iid,
            "title": mr.title,
            "author_name": mr.author.name,
            "author_username": mr.author.username,
            "author_avatar": mr.author.avatar_url,
            "target_branch": mr.target_branch,
            "labels": json.dumps(request.get("labels", mr.labels)),
            "is_hotfix": int(request["is_hotfix"]),
        }
        pending = json.dumps({**request, "token": uuid4().hex, "params": params})
        async with self.db.transaction() as session:
            result = await session.execute(
                text("SELECT requeue_request FROM merge_requests WHERE project_id = :project_id AND id = :id"),
                {"project_id": project_id, "id": request["queue_id"]},
            )
            saved = result.scalar_one_or_none()
            if self._older_requeue_request(request, saved):
                return
            await session.execute(
                text(
                    "UPDATE merge_requests SET requeue_request = :pending WHERE project_id = :project_id "
                    "AND id = :id AND pending_completion IS NOT NULL AND (requeue_request = :saved "
                    "OR (requeue_request IS NULL AND :saved IS NULL))"
                ),
                {"pending": pending, "project_id": project_id, "id": request["queue_id"], "saved": saved},
            )

    def _older_requeue_request(self, request: dict[str, Any], saved: str | None) -> bool:
        event_at = request.get("requested_at")
        if saved is None or event_at is None:
            return False
        previous = json.loads(saved)
        times = [
            time for time in [previous.get("requested_at"), *previous.get("cancelled_events", [])] if time is not None
        ]
        return bool(times) and event_at <= max(times)

    async def cancel_requeue(self, project_id: int, queue_id: int, event_at: datetime) -> None:
        async with self.db.transaction() as session:
            result = await session.execute(
                text("SELECT requeue_request FROM merge_requests WHERE project_id = :project_id AND id = :id"),
                {"project_id": project_id, "id": queue_id},
            )
            saved = result.scalar_one_or_none()
            if saved is None:
                return
            request = json.loads(saved)
            requested_at = request.get("requested_at")
            if requested_at is not None and event_at <= datetime.fromisoformat(requested_at):
                return
            request["cancelled_events"] = [*request.get("cancelled_events", []), event_at.isoformat()]
            request["token"] = uuid4().hex
            await session.execute(
                text(
                    "UPDATE merge_requests SET requeue_request = :request WHERE project_id = :project_id AND id = :id "
                    "AND requeue_request = :saved AND pending_completion IS NOT NULL"
                ),
                {"request": json.dumps(request), "saved": saved, "project_id": project_id, "id": queue_id},
            )

    async def _stage_completion_positions(
        self, session: Any, project_id: int, positions: dict[str, int], old_total: int
    ) -> None:
        result = await session.execute(
            text(_SELECT_ACTIVE_QUEUE_PROJECT_SQL + _SELECT_ACTIVE_QUEUE_ORDER_SQL), {"project_id": project_id}
        )
        rows = list(result.mappings())
        for position, row in enumerate(rows, 1):
            previous = positions.get(str(row["iid"]))
            if row["status"] != "queued" or previous is None or row["pending_notification"] is not None:
                continue
            if previous == position and old_total == len(rows):
                continue
            pending = json.dumps(
                {
                    "token": uuid4().hex,
                    "status": "position_changed" if previous != position else "total_changed",
                    "old_position": previous,
                    "old_total": old_total,
                }
            )
            await session.execute(
                text("UPDATE merge_requests SET pending_notification = :pending WHERE id = :id"),
                {"pending": pending, "id": row["id"]},
            )

    async def stage_completion_positions(self, project_id: int, positions: dict[int, int], old_total: int) -> None:
        async with self.db.transaction() as session:
            await self._stage_completion_positions(
                session, project_id, {str(k): v for k, v in positions.items()}, old_total
            )

    async def finalize_completion(self, project_id: int, item: QueueItem, payload: dict[str, Any]) -> bool:
        """Archive and delete only this intent's incarnation; transfer any requeue atomically."""
        async with self.db.transaction() as session:
            result = await session.execute(
                text(
                    "DELETE FROM merge_requests WHERE project_id = :project_id AND id = :id "
                    "AND pending_completion = :pending AND (requeue_request = :requeue "
                    "OR (requeue_request IS NULL AND :requeue IS NULL)) RETURNING id"
                ),
                {
                    "project_id": project_id,
                    "id": item.queue_id,
                    "pending": json.dumps(payload),
                    "requeue": item.requeue_request,
                },
            )
            if result.first() is None:
                return False
            await session.execute(
                text(_INSERT_HISTORY_SQL + " ON CONFLICT(project_id, iid) DO NOTHING"), payload["history"]
            )
            requeue = json.loads(item.requeue_request) if item.requeue_request is not None else None
            if requeue is not None and not requeue_is_cancelled(requeue, payload["label_events"]):
                await session.execute(
                    text(_INSERT_MR_SQL), {**requeue["params"], "queued_at": datetime.now(UTC).isoformat()}
                )
                await session.execute(
                    text(
                        "UPDATE merge_requests SET pending_notification = :pending, ignored_label_events = :ignored WHERE project_id = :project_id AND iid = :iid"
                    ),
                    {
                        "pending": json.dumps({"token": uuid4().hex, "status": "queued", "old_position": 0}),
                        "ignored": json.dumps(payload["label_events"]),
                        "project_id": project_id,
                        "iid": item.mr_iid,
                    },
                )
            request = payload["request"]
            await self._stage_completion_positions(session, project_id, request["positions"], request["old_total"])
        self._cache.invalidate()
        return True

    async def complete_mr(
        self,
        project_id: int,
        mr_iid: int,
        status: str,
        failure_reason: str | None = None,
        pipeline_duration_seconds: int | None = None,
        pipeline_failed_jobs: list[str] | None = None,
        *,
        expected_queue_id: int | None = None,
    ) -> bool:
        """Atomically archive the requested incarnation, never an owned completion or replacement."""
        request = CompletionRequest(
            status, status, "", {}, failure_reason, pipeline_duration_seconds, pipeline_failed_jobs
        )
        async with self.db.transaction() as session:
            result = await session.execute(
                text(
                    "DELETE FROM merge_requests WHERE project_id = :project_id AND iid = :iid "
                    "AND pending_completion IS NULL AND (:expected_id IS NULL OR id = :expected_id) RETURNING *"
                ),
                {"project_id": project_id, "iid": mr_iid, "expected_id": expected_queue_id},
            )
            row = result.mappings().one_or_none()
            if row is None:
                self._cache.invalidate()
                return False
            item = self._row_to_queue_item(row)
            params = self._history_params(item, request, datetime.now(UTC))
            await session.execute(text(_INSERT_HISTORY_SQL + " ON CONFLICT(project_id, iid) DO NOTHING"), params)
        self._cache.invalidate()
        OPERATIONS_TOTAL.labels(project_id=str(project_id), type="complete", status="success").inc()
        return True

    async def get_queue_stats(self, project_id: int | None = None) -> dict[str, int]:
        """Get statistics about the active queue.

        Args:
            project_id: Filter by project ID. None returns stats for all projects.

        Returns:
            Dict mapping status to count for active states.
            Example: {"queued": 5, "rebasing": 1, "testing": 2, "merging": 0}
        """
        if project_id is not None:
            sql = _SELECT_QUEUE_STATS_BASE_SQL + _SELECT_QUEUE_STATS_PROJECT_SQL + _SELECT_QUEUE_STATS_GROUP_SQL
            params: dict[str, Any] = {"project_id": project_id}
        else:
            sql = _SELECT_QUEUE_STATS_BASE_SQL + _SELECT_QUEUE_STATS_GROUP_SQL
            params = {}

        async with self.db.session() as session:
            result = await session.execute(text(sql), params)
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

    async def get_recent_history(
        self,
        limit: int = 10,
        project_id: int | None = None,
    ) -> list[QueueItem]:
        """Get recently completed MRs for dashboard history.

        Returns MRs with status in ('merged', 'failed', 'removed') that have
        a finished_at timestamp, ordered by most recent first.

        Args:
            limit: Maximum number of items to return (default: 10).
            project_id: Filter by project ID. None returns history for all projects.

        Returns:
            List of QueueItems ordered by finished_at descending.
        """
        log.debug("Getting recent history", limit=limit, project_id=project_id)

        if project_id is not None:
            sql = _SELECT_RECENT_HISTORY_BASE_SQL + _SELECT_RECENT_HISTORY_PROJECT_SQL + _SELECT_RECENT_HISTORY_TAIL_SQL
            params: dict[str, Any] = {"limit": limit, "project_id": project_id}
        else:
            sql = _SELECT_RECENT_HISTORY_BASE_SQL + _SELECT_RECENT_HISTORY_TAIL_SQL
            params = {"limit": limit}

        async with self.db.session() as session:
            result = await session.execute(text(sql), params)
            rows = result.mappings().all()
            await session.commit()

        history = [self._row_to_queue_item(row) for row in rows]
        log.debug("Recent history retrieved", count=len(history))
        return history

    async def get_dashboard_stats(
        self,
        days: int = 7,
        project_id: int | None = None,
    ) -> DashboardStats:
        """Get aggregate statistics for dashboard display.

        Computes statistics over a rolling window of completed MRs.

        Args:
            days: Number of days to include in statistics (default: 7).
            project_id: Filter by project ID. None returns stats for all projects.

        Returns:
            DashboardStats with success rate and timing metrics.
        """
        log.debug("Getting dashboard stats", days=days, project_id=project_id)

        if project_id is not None:
            sql = _SELECT_STATS_WINDOW_BASE_SQL + _SELECT_STATS_WINDOW_PROJECT_SQL
            params: dict[str, Any] = {"days_param": f"-{days} days", "project_id": project_id}
        else:
            sql = _SELECT_STATS_WINDOW_BASE_SQL
            params = {"days_param": f"-{days} days"}

        async with self.db.session() as session:
            result = await session.execute(text(sql), params)
            row = result.mappings().one()
            await session.commit()

        merged_count = int(row["merged_count"] or 0)
        total_completed = int(row["total_completed"] or 0)
        success_rate = (merged_count / total_completed * 100) if total_completed > 0 else 0.0

        total_in_queue = await self.get_queue_length(project_id)

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

    async def cleanup_old_entries(self, project_id: int, days: int = 90) -> int:
        """Delete queue entries older than specified days.

        Only deletes entries that have a finished_at timestamp (completed MRs).
        Active MRs are never deleted regardless of age.

        Args:
            project_id: The GitLab project ID.
            days: Number of days after which to delete entries (default: 90).

        Returns:
            Number of entries deleted.
        """
        log.debug("Cleaning up old queue entries", project_id=project_id, days=days)

        async with self.db.transaction() as session:
            cursor_result = await session.execute(
                text(_CLEANUP_OLD_ENTRIES_SQL),
                {"days_param": f"-{days} days", "project_id": project_id},
            )
            deleted_count: int = cursor_result.rowcount  # type: ignore[attr-defined]

        if deleted_count > 0:
            log.info("Old queue entries cleaned up", deleted_count=deleted_count, days=days)
        else:
            log.debug("No old entries to clean up")

        return deleted_count

    async def get_stale_mrs(self, project_id: int, hours: int) -> list[QueueItem]:
        """Get MRs that have been in queue longer than specified hours.

        Only returns MRs that haven't received a stale warning yet.

        Args:
            project_id: The GitLab project ID.
            hours: Threshold in hours.

        Returns:
            List of QueueItem objects that exceed the threshold and haven't been warned.
        """
        log.debug("Checking for stale MRs", project_id=project_id, hours=hours)

        async with self.db.session() as session:
            result = await session.execute(
                text(_SELECT_STALE_MRS_SQL),
                {"hours_param": f"-{hours} hours", "project_id": project_id},
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

    async def mark_stale_warning_sent(self, project_id: int, mr_iid: int) -> bool:
        """Mark that stale warning has been sent for an MR.

        Args:
            project_id: The GitLab project ID.
            mr_iid: The MR's internal ID.

        Returns:
            True if updated, False if MR not found.
        """
        log.debug("Marking stale warning sent", project_id=project_id, mr_iid=mr_iid)

        async with self.db.transaction() as session:
            cursor_result = await session.execute(
                text(_MARK_STALE_WARNING_SENT_SQL),
                {"iid": mr_iid, "project_id": project_id},
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
            project_id=row.get("project_id", 0),
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
            processing_attempts=row.get("processing_attempts", 0) or 0,
            queue_id=row.get("id", 0),
            metadata_version=row.get("metadata_version", 0),
            pending_notification=row.get("pending_notification"),
            pending_completion=row.get("pending_completion"),
            requeue_request=row.get("requeue_request"),
            ignored_label_events=json.loads(row.get("ignored_label_events") or "[]"),
        )


__all__: list[str] = [
    "QueueError",
    "QueueItemNotFoundError",
    "QueueManager",
]
