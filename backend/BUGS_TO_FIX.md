# Bugs to Fix in GitLab Merge Queue Bot

This document contains identified bugs that need to be fixed. Each bug includes full context for an AI agent to implement the fix.

---

## Bug 1: Race Condition in QueueCache (HIGH PRIORITY)

**File:** `src/gitlab_queue/core/queue.py`
**Lines:** 200-221

**Problem:** The `QueueCache` dataclass has no async lock protecting concurrent access. Multiple async tasks (processor, scheduler, webhook handlers) can read stale cache data or corrupt the cache state when calling `invalidate()` and reading `_active_queue` simultaneously.

**Current Code:**
```python
@dataclass
class QueueCache:
    """Cache for queue data to reduce database queries."""

    _active_queue: list[QueueItem] | None = field(default=None)
    _last_refresh: datetime | None = field(default=None)
    _cache_ttl_seconds: float = field(default=5.0)

    def invalidate(self) -> None:
        """Invalidate the cache, forcing a refresh on next access."""
        self._active_queue = None
        self._last_refresh = None
```

**Fix Required:**
1. Add `asyncio.Lock` field to `QueueCache`
2. Create async `invalidate()` method that acquires lock
3. Create async method to safely get/set cache data
4. Update all callers to use async invalidate

**Example Fix:**
```python
@dataclass
class QueueCache:
    """Cache for queue data to reduce database queries."""

    _active_queue: list[QueueItem] | None = field(default=None)
    _last_refresh: datetime | None = field(default=None)
    _cache_ttl_seconds: float = field(default=5.0)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def invalidate(self) -> None:
        """Invalidate the cache, forcing a refresh on next access."""
        async with self._lock:
            self._active_queue = None
            self._last_refresh = None

    async def get_cached(self) -> tuple[list[QueueItem] | None, bool]:
        """Get cached data if valid. Returns (data, is_valid)."""
        async with self._lock:
            if self._active_queue is None or self._last_refresh is None:
                return None, False
            if (datetime.now(UTC) - self._last_refresh).total_seconds() > self._cache_ttl_seconds:
                return None, False
            return self._active_queue, True

    async def set_cached(self, items: list[QueueItem]) -> None:
        """Set cached data."""
        async with self._lock:
            self._active_queue = items
            self._last_refresh = datetime.now(UTC)
```

**Callers to update:**
- Line 327: `self._cache.invalidate()` -> `await self._cache.invalidate()`
- Line 360: `self._cache.invalidate()` -> `await self._cache.invalidate()`
- Line 546: `self._cache.invalidate()` -> `await self._cache.invalidate()`
- Line 727: `self._cache.invalidate()` -> `await self._cache.invalidate()`

---

## ~~Bug 2: Unhandled Pipeline Statuses Cause Infinite Loop~~ (FIXED)

**Status:** FIXED

**Fix applied:** Added handling for non-actionable pipeline statuses (`skipped`, `manual`, `waiting_for_resource`, `blocked`) in `_wait_for_pipeline` method. These statuses now trigger `pipeline_failed` with a descriptive error message instead of looping indefinitely.

---

## Bug 4: JSON Parsing Error Not Handled in _row_to_queue_item (MEDIUM PRIORITY)

**File:** `src/gitlab_queue/core/queue.py`
**Lines:** 755-762

**Problem:** If the `labels` column in the database contains invalid JSON, `json.loads()` will raise `JSONDecodeError` and crash the application.

**Current Code:**
```python
labels_raw = row.get("labels")
if labels_raw is None:
    labels = []
elif isinstance(labels_raw, str):
    labels = json.loads(labels_raw) if labels_raw else []  # BUG: no try/except
else:
    labels = list(labels_raw) if labels_raw else []
```

**Fix Required:**
```python
labels_raw = row.get("labels")
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
                labels_raw=labels_raw[:100] if len(labels_raw) > 100 else labels_raw,
            )
            labels = []
else:
    labels = list(labels_raw) if labels_raw else []
```

---

## Bug 5: Schema Migration Swallows All Exceptions (MEDIUM PRIORITY)

**File:** `src/gitlab_queue/core/queue.py`
**Lines:** 266-271

**Problem:** The migration catches all exceptions with bare `except Exception` and silently ignores them. This could hide real database errors (connection issues, permission problems, SQL errors).

**Current Code:**
```python
try:
    await session.execute(text(_ALTER_TABLE_STALE_WARNING_SQL))
    log.info("Added stale_warning_sent column to merge_requests table")
except Exception:
    # Column already exists - ignore
    pass
```

**Fix Required:**
```python
from sqlalchemy.exc import OperationalError, ProgrammingError

try:
    await session.execute(text(_ALTER_TABLE_STALE_WARNING_SQL))
    log.info("Added stale_warning_sent column to merge_requests table")
except (OperationalError, ProgrammingError) as e:
    error_msg = str(e).lower()
    if "duplicate column" in error_msg or "already exists" in error_msg:
        log.debug("Column stale_warning_sent already exists, skipping migration")
    else:
        log.error("Failed to add stale_warning_sent column", error=str(e))
        raise
```

---

## Bug 6: Label Changes None Handling in Webhook Handlers (MEDIUM PRIORITY)

**File:** `src/gitlab_queue/webhooks/handlers.py`
**Lines:** 199-227 (methods `_is_queue_label_added` and `_is_queue_label_removed`)

**Problem:** If `event.label_changes.current` or `event.label_changes.previous` is `None` instead of an empty list, `set()` conversion will fail with TypeError.

**Current Code:**
```python
def _is_queue_label_added(self, event: MRWebhookEvent) -> bool:
    if event.label_changes is None:
        return False
    # BUG: current or previous could be None
    added = set(event.label_changes.current) - set(event.label_changes.previous)
    return self.settings.queue_label in added
```

**Fix Required:**
```python
def _is_queue_label_added(self, event: MRWebhookEvent) -> bool:
    if event.label_changes is None:
        return False
    current = set(event.label_changes.current or [])
    previous = set(event.label_changes.previous or [])
    added = current - previous
    return self.settings.queue_label in added

def _is_queue_label_removed(self, event: MRWebhookEvent) -> bool:
    if event.label_changes is None:
        return False
    current = set(event.label_changes.current or [])
    previous = set(event.label_changes.previous or [])
    removed = previous - current
    return self.settings.queue_label in removed
```

---

## Bug 7: WebSocket Connections Not Gracefully Closed on Shutdown (LOW PRIORITY)

**File:** `src/gitlab_queue/api/websocket.py`
**Lines:** 63-65

**Problem:** `WebSocketManager` has no method to gracefully close all connections during server shutdown. Connections are forcefully terminated when uvicorn shuts down.

**Current Code:**
```python
class WebSocketManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
    # No close_all method
```

**Fix Required:**
```python
class WebSocketManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def close_all(self, reason: str = "Server shutting down") -> None:
        """Close all WebSocket connections gracefully."""
        log = get_logger(__name__)
        connections = list(self._connections)  # Copy to avoid modification during iteration

        for ws in connections:
            try:
                await ws.close(code=1001, reason=reason)
            except Exception as e:
                log.debug("Error closing WebSocket", error=str(e))

        self._connections.clear()
        log.info("Closed all WebSocket connections", count=len(connections))
```

**Also update** `src/gitlab_queue/main.py` to call `websocket_manager.close_all()` during shutdown.

---

## Testing After Fixes

After implementing fixes, run:

```bash
cd backend
make check      # Lint + typecheck
make test       # All tests
```

Ensure no regressions in existing functionality.
