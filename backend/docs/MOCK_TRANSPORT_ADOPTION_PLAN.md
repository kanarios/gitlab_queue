# MockTransport Adoption Plan

## Background

Based on James Bennett's article ["Don't mock Python's HTTPX"](https://www.b-list.org/weblog/2023/dec/08/mock-python-httpx/), we're migrating from JJ remote mock server to httpx's built-in `MockTransport`.

### Key Principles

1. **Don't mock what you don't own** - instead of patching httpx internals, inject a mock transport
2. **Refactor code to accept transport** - `GitLabClient` should accept an optional transport parameter
3. **Use httpx.MockTransport** - built-in mechanism designed for testing

### Current Problems

| Approach | Location | Issue |
|----------|----------|-------|
| JJ Remote Mock | `scenarios/mocks/gitlab/` | Requires external mock server running |
| MagicMock/AsyncMock | `scenarios/webhooks/*/_helpers.py` | Mocks entire GitLabClient - violates "don't mock what you don't own" |
| GitLabClient | `src/gitlab_queue/clients/gitlab.py` | Creates httpx.AsyncClient internally, no transport injection |

---

## Phase 1: Modify GitLabClient for Transport Injection

### 1.1 Update GitLabClient Constructor

**File:** `src/gitlab_queue/clients/gitlab.py`

```python
def __init__(
    self, 
    settings: Settings,
    transport: httpx.AsyncBaseTransport | None = None,  # NEW
) -> None:
    """Initialize GitLab client with settings.

    Args:
        settings: Application settings with GitLab configuration.
        transport: Optional custom transport for testing. If None, uses default.
    """
    self._settings = settings
    # ... existing code ...
    
    self._client = httpx.AsyncClient(
        base_url=self._base_url,
        headers={
            "Private-Token": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=httpx.Timeout(30.0, connect=10.0),
        transport=transport,  # NEW - use custom transport if provided
    )
```

### 1.2 Acceptance Criteria

- [ ] `GitLabClient` accepts optional `transport` parameter
- [ ] Production code unchanged (transport=None uses default)
- [ ] All existing tests still pass
- [ ] Type hints updated

---

## Phase 2: Create MockTransport Factory

### 2.1 New Directory Structure

```
scenarios/transports/
├── __init__.py
├── gitlab_mock_transport.py      # Main mock transport implementation
├── request_matcher.py            # URL/method matching utilities
└── responses/                    # Response factories by domain
    ├── __init__.py
    ├── mr_responses.py           # MergeRequest responses
    ├── pipeline_responses.py     # Pipeline responses
    ├── note_responses.py         # Notes/comments responses
    └── error_responses.py        # Error responses (404, 429, 500, etc.)
```

### 2.2 GitLabMockTransport Implementation

```python
from typing import Callable
import httpx
import re

ResponseHandler = Callable[[httpx.Request], httpx.Response]

class GitLabMockTransport(httpx.MockTransport):
    """Mock transport for GitLab API testing.
    
    Provides fluent API for registering responses and supports:
    - Exact path matching
    - Regex path patterns
    - Response sequences (for retry testing)
    - Request history tracking
    
    Example:
        transport = GitLabMockTransport()
        transport.register_get(
            "/api/v4/projects/123/merge_requests/42",
            json={"iid": 42, "title": "Test MR", ...}
        )
        
        client = GitLabClient(settings, transport=transport)
        mr = await client.get_mr(42)  # Returns mocked response
    """
    
    def __init__(self) -> None:
        self._handlers: list[tuple[str, str | re.Pattern, ResponseHandler]] = []
        self._history: list[httpx.Request] = []
        self._default_handler: ResponseHandler = self._not_found
        super().__init__(self._dispatch)
    
    def register(
        self,
        method: str,
        path: str | re.Pattern,
        *,
        status: int = 200,
        json: dict | list | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> "GitLabMockTransport":
        """Register a response for method + path combination."""
        response = httpx.Response(
            status_code=status,
            json=json,
            content=content,
            headers=headers or {},
        )
        self._handlers.append((method, path, lambda r: response))
        return self  # Fluent API
    
    def register_get(self, path: str | re.Pattern, **kwargs) -> "GitLabMockTransport":
        return self.register("GET", path, **kwargs)
    
    def register_post(self, path: str | re.Pattern, **kwargs) -> "GitLabMockTransport":
        return self.register("POST", path, **kwargs)
    
    def register_put(self, path: str | re.Pattern, **kwargs) -> "GitLabMockTransport":
        return self.register("PUT", path, **kwargs)
    
    def register_sequence(
        self,
        method: str,
        path: str | re.Pattern,
        responses: list[httpx.Response],
    ) -> "GitLabMockTransport":
        """Register a sequence of responses (for retry/polling tests)."""
        iterator = iter(responses)
        def handler(request: httpx.Request) -> httpx.Response:
            return next(iterator, self._not_found(request))
        self._handlers.append((method, path, handler))
        return self
    
    @property
    def history(self) -> list[httpx.Request]:
        """Return list of all requests made through this transport."""
        return self._history.copy()
    
    def _dispatch(self, request: httpx.Request) -> httpx.Response:
        """Find matching handler and return response."""
        self._history.append(request)
        
        for method, path_pattern, handler in self._handlers:
            if request.method != method:
                continue
            
            path = request.url.path
            if isinstance(path_pattern, re.Pattern):
                if path_pattern.match(path):
                    return handler(request)
            elif path == path_pattern:
                return handler(request)
        
        return self._default_handler(request)
    
    def _not_found(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=404,
            json={"message": f"No mock registered for {request.method} {request.url.path}"}
        )
```

### 2.3 Response Factories

**File:** `scenarios/transports/responses/mr_responses.py`

```python
def mr_response(
    iid: int,
    *,
    title: str = "Test MR",
    state: str = "opened",
    sha: str = "abc123",
    source_branch: str = "feature",
    target_branch: str = "main",
    merge_status: str = "can_be_merged",
    has_conflicts: bool = False,
    rebase_in_progress: bool = False,
    labels: list[str] | None = None,
    author_id: int = 1,
    author_name: str = "Test User",
    author_username: str = "testuser",
    project_id: int = 123,
) -> dict:
    """Create a valid MR response dictionary."""
    return {
        "iid": iid,
        "project_id": project_id,
        "title": title,
        "state": state,
        "sha": sha,
        "source_branch": source_branch,
        "target_branch": target_branch,
        "merge_status": merge_status,
        "has_conflicts": has_conflicts,
        "rebase_in_progress": rebase_in_progress,
        "labels": labels or [],
        "author": {
            "id": author_id,
            "name": author_name,
            "username": author_username,
        },
        "web_url": f"https://gitlab.com/test/project/-/merge_requests/{iid}",
    }
```

### 2.4 Acceptance Criteria

- [ ] `GitLabMockTransport` class implemented
- [ ] Request history tracking works
- [ ] Response sequences work (for retry tests)
- [ ] Regex path matching works
- [ ] Response factories created for all domains (MR, Pipeline, Notes, etc.)

---

## Phase 3: Migrate Tests

### 3.1 Update Test Client Factory

**File:** `scenarios/contexts/gitlab_client_factory.py`

```python
def created_test_client(
    transport: httpx.AsyncBaseTransport | None = None,
    project_id: int = TEST_PROJECT_ID,
) -> GitLabClient:
    """Create GitLabClient configured for testing.
    
    Args:
        transport: Custom transport (MockTransport for unit tests).
        project_id: GitLab project ID (default: 123).
    
    Returns:
        GitLabClient instance.
    """
    settings = created_test_settings(project_id=project_id)
    return GitLabClient(settings, transport=transport)
```

### 3.2 Migration Order (Simple to Complex)

| Priority | Test Category | Files | Approach |
|----------|--------------|-------|----------|
| 1 | Webhook handlers | `scenarios/webhooks/*/` | Replace MagicMock with real client + MockTransport |
| 2 | Unit tests | `scenarios/unit/` | Add MockTransport where GitLabClient is used |
| 3 | Integration (simple) | `scenarios/integration/webhook_*.py` | Replace JJ mocked() with MockTransport |
| 4 | Integration (complex) | `scenarios/integration/full_flow*.py` | Replace JJ with response sequences |

### 3.3 Example Migration: Webhook Handler Test

**Before (MagicMock):**
```python
def given_handler(self):
    self.gitlab_client = MagicMock()
    self.gitlab_client.get_mr = AsyncMock(return_value=MergeRequest(...))
    self.handler = MRWebhookHandler(
        gitlab_client=self.gitlab_client,
        ...
    )
```

**After (MockTransport):**
```python
def given_handler(self):
    self.transport = GitLabMockTransport()
    self.transport.register_get(
        "/api/v4/projects/123/merge_requests/42",
        json=mr_response(iid=42, title="Test MR")
    )
    self.gitlab_client = created_test_client(transport=self.transport)
    self.handler = MRWebhookHandler(
        gitlab_client=self.gitlab_client,
        ...
    )
```

### 3.4 Acceptance Criteria

- [ ] All webhook handler tests migrated
- [ ] All unit tests migrated  
- [ ] All integration tests migrated
- [ ] Test execution time improved (no network overhead)
- [ ] No flaky tests due to mock server timing

---

## Phase 4: Protocol/Interface Pattern for Internal Dependencies

While MockTransport solves the GitLab API mocking problem, we still have `MagicMock` usage for internal dependencies like `QueueManager`. To fully eliminate monkey-patching, we introduce Protocol-based interfaces.

### 4.1 Current Problem

```python
# scenarios/webhooks/mr_webhook/_helpers.py
def create_mock_queue_manager():
    qm = MagicMock()
    qm.add_to_queue = AsyncMock()
    qm.remove_from_queue = AsyncMock(return_value=True)
    ...
```

This violates "don't mock what you don't own" because we're mocking our own class with MagicMock instead of using a proper test double.

### 4.2 Solution: Protocol + Fake Implementation

**Step 1: Define Protocol** (`src/gitlab_queue/core/protocols.py`)

```python
from typing import Protocol, Any
from datetime import datetime

from gitlab_queue.models.mr import MergeRequest
from gitlab_queue.models.queue_item import QueueItem, DashboardStats


class QueueManagerProtocol(Protocol):
    """Protocol defining the QueueManager interface.
    
    Use this protocol for type hints when you need to accept
    either real QueueManager or FakeQueueManager for testing.
    """

    async def ensure_schema(self) -> None: ...
    
    async def add_to_queue(
        self,
        mr: MergeRequest,
        is_hotfix: bool = False,
    ) -> QueueItem: ...
    
    async def remove_from_queue(self, mr_iid: int) -> bool: ...
    
    async def get_queue_position(self, mr_iid: int) -> int | None: ...
    
    async def get_next_mr(self) -> QueueItem | None: ...
    
    async def get_queue_item(self, mr_iid: int) -> QueueItem | None: ...
    
    async def get_active_queue(self) -> list[QueueItem]: ...
    
    async def get_queue_length(self) -> int: ...
    
    async def get_mr_state(self, mr_iid: int) -> dict[str, Any] | None: ...
    
    async def update_mr_state(
        self,
        mr_iid: int,
        state: str,
        **extra: Any,
    ) -> bool: ...
    
    async def complete_mr(
        self,
        mr_iid: int,
        status: str,
        failure_reason: str | None = None,
        pipeline_duration_seconds: int | None = None,
        pipeline_failed_jobs: list[str] | None = None,
    ) -> bool: ...
    
    async def get_queue_stats(self) -> dict[str, int]: ...
    
    async def get_recent_history(self, limit: int = 10) -> list[QueueItem]: ...
    
    async def get_dashboard_stats(self, days: int = 7) -> DashboardStats: ...
    
    async def cleanup_old_entries(self, days: int = 90) -> int: ...
    
    async def get_stale_mrs(self, hours: int) -> list[QueueItem]: ...
    
    async def mark_stale_warning_sent(self, mr_iid: int) -> bool: ...
```

**Step 2: Create FakeQueueManager** (`scenarios/fakes/queue_manager.py`)

```python
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from gitlab_queue.core.protocols import QueueManagerProtocol
from gitlab_queue.core.queue import QueueItemNotFoundError
from gitlab_queue.models.mr import MergeRequest
from gitlab_queue.models.queue_item import DashboardStats, QueueItem


@dataclass
class FakeQueueManager:
    """In-memory fake implementation of QueueManager for testing.
    
    Implements QueueManagerProtocol without database dependency.
    All data is stored in memory and lost when instance is discarded.
    
    Example:
        queue = FakeQueueManager()
        await queue.add_to_queue(mr, is_hotfix=False)
        item = await queue.get_next_mr()
    """
    
    _items: dict[int, QueueItem] = field(default_factory=dict)
    _history: list[QueueItem] = field(default_factory=list)
    _id_counter: int = field(default=0)
    
    async def ensure_schema(self) -> None:
        """No-op for fake - no schema to create."""
        pass
    
    async def add_to_queue(
        self,
        mr: MergeRequest,
        is_hotfix: bool = False,
    ) -> QueueItem:
        """Add MR to in-memory queue."""
        if mr.iid in self._items:
            return self._items[mr.iid]
        
        self._id_counter += 1
        now = datetime.now(UTC)
        
        item = QueueItem(
            mr_iid=mr.iid,
            title=mr.title,
            author_name=mr.author.name,
            author_username=mr.author.username,
            author_avatar=mr.author.avatar_url,
            target_branch=mr.target_branch,
            state="queued",
            queued_at=now,
            is_hotfix=is_hotfix,
            labels=mr.labels,
        )
        self._items[mr.iid] = item
        return item
    
    async def remove_from_queue(self, mr_iid: int) -> bool:
        """Mark MR as removed."""
        if mr_iid not in self._items:
            return False
        
        item = self._items[mr_iid]
        if item.state == "removed":
            return False
        
        # Update state to removed
        self._items[mr_iid] = QueueItem(
            mr_iid=item.mr_iid,
            title=item.title,
            author_name=item.author_name,
            author_username=item.author_username,
            author_avatar=item.author_avatar,
            target_branch=item.target_branch,
            state="removed",
            queued_at=item.queued_at,
            started_at=item.started_at,
            finished_at=datetime.now(UTC),
            is_hotfix=item.is_hotfix,
            labels=item.labels,
        )
        return True
    
    async def get_queue_position(self, mr_iid: int) -> int | None:
        """Get position in queue (1-indexed)."""
        queue = await self.get_active_queue()
        for i, item in enumerate(queue):
            if item.mr_iid == mr_iid:
                return i + 1
        return None
    
    async def get_next_mr(self) -> QueueItem | None:
        """Get next MR with 'queued' status."""
        queue = await self.get_active_queue()
        for item in queue:
            if item.state == "queued":
                return item
        return None
    
    async def get_queue_item(self, mr_iid: int) -> QueueItem | None:
        """Get queue item by MR IID."""
        return self._items.get(mr_iid)
    
    async def get_active_queue(self) -> list[QueueItem]:
        """Get all active items, sorted by hotfix priority and queue time."""
        active_states = {"queued", "rebasing", "testing", "merging"}
        active = [item for item in self._items.values() if item.state in active_states]
        # Sort: hotfix first, then by queued_at
        return sorted(active, key=lambda x: (not x.is_hotfix, x.queued_at))
    
    async def get_queue_length(self) -> int:
        """Get count of active items."""
        return len(await self.get_active_queue())
    
    async def get_mr_state(self, mr_iid: int) -> dict[str, Any] | None:
        """Get MR state dict."""
        item = self._items.get(mr_iid)
        if item is None:
            # Check history
            for hist_item in reversed(self._history):
                if hist_item.mr_iid == mr_iid:
                    return {
                        "status": hist_item.state,
                        "started_at": hist_item.started_at,
                        "last_error": hist_item.last_error,
                        "finished_at": hist_item.finished_at,
                    }
            return None
        
        return {
            "status": item.state,
            "started_at": item.started_at,
            "last_error": item.last_error,
            "finished_at": item.finished_at,
        }
    
    async def update_mr_state(
        self,
        mr_iid: int,
        state: str,
        **extra: Any,
    ) -> bool:
        """Update MR state."""
        if mr_iid not in self._items:
            raise QueueItemNotFoundError(mr_iid)
        
        item = self._items[mr_iid]
        now = datetime.now(UTC)
        terminal_states = {"merged", "failed", "removed"}
        
        self._items[mr_iid] = QueueItem(
            mr_iid=item.mr_iid,
            title=item.title,
            author_name=item.author_name,
            author_username=item.author_username,
            author_avatar=item.author_avatar,
            target_branch=item.target_branch,
            state=state,
            queued_at=item.queued_at,
            started_at=item.started_at or now,
            finished_at=now if state in terminal_states else item.finished_at,
            is_hotfix=item.is_hotfix,
            labels=item.labels,
            pipeline_id=extra.get("pipeline_id", item.pipeline_id),
            pipeline_status=extra.get("pipeline_status", item.pipeline_status),
            retry_count=extra.get("retry_count", item.retry_count),
            last_error=extra.get("last_error", item.last_error),
        )
        return True
    
    async def complete_mr(
        self,
        mr_iid: int,
        status: str,
        failure_reason: str | None = None,
        pipeline_duration_seconds: int | None = None,
        pipeline_failed_jobs: list[str] | None = None,
    ) -> bool:
        """Move MR from active to history."""
        if mr_iid not in self._items:
            return False
        
        item = self._items.pop(mr_iid)
        now = datetime.now(UTC)
        
        completed_item = QueueItem(
            mr_iid=item.mr_iid,
            title=item.title,
            author_name=item.author_name,
            author_username=item.author_username,
            author_avatar=item.author_avatar,
            target_branch=item.target_branch,
            state=status,
            queued_at=item.queued_at,
            started_at=item.started_at,
            finished_at=now,
            is_hotfix=item.is_hotfix,
            labels=item.labels,
            last_error=failure_reason,
        )
        self._history.append(completed_item)
        return True
    
    async def get_queue_stats(self) -> dict[str, int]:
        """Get stats by status."""
        stats = {"queued": 0, "rebasing": 0, "testing": 0, "merging": 0}
        for item in self._items.values():
            if item.state in stats:
                stats[item.state] += 1
        return stats
    
    async def get_recent_history(self, limit: int = 10) -> list[QueueItem]:
        """Get recent completed items."""
        return list(reversed(self._history[-limit:]))
    
    async def get_dashboard_stats(self, days: int = 7) -> DashboardStats:
        """Get dashboard statistics."""
        merged = sum(1 for item in self._history if item.state == "merged")
        failed = sum(1 for item in self._history if item.state == "failed")
        total = merged + failed
        
        return DashboardStats(
            total_in_queue=await self.get_queue_length(),
            merged_count=merged,
            failed_count=failed,
            success_rate=round(merged / total * 100, 1) if total > 0 else 0.0,
            avg_wait_seconds=0.0,
            avg_processing_seconds=0.0,
            stats_window_days=days,
        )
    
    async def cleanup_old_entries(self, days: int = 90) -> int:
        """No-op for fake - nothing to clean up."""
        return 0
    
    async def get_stale_mrs(self, hours: int) -> list[QueueItem]:
        """Get MRs queued longer than hours."""
        threshold = datetime.now(UTC).timestamp() - (hours * 3600)
        return [
            item for item in self._items.values()
            if item.queued_at.timestamp() < threshold
            and not item.stale_warning_sent
        ]
    
    async def mark_stale_warning_sent(self, mr_iid: int) -> bool:
        """Mark stale warning as sent."""
        if mr_iid not in self._items:
            return False
        
        item = self._items[mr_iid]
        self._items[mr_iid] = QueueItem(
            mr_iid=item.mr_iid,
            title=item.title,
            author_name=item.author_name,
            author_username=item.author_username,
            author_avatar=item.author_avatar,
            target_branch=item.target_branch,
            state=item.state,
            queued_at=item.queued_at,
            started_at=item.started_at,
            finished_at=item.finished_at,
            is_hotfix=item.is_hotfix,
            labels=item.labels,
            stale_warning_sent=True,
        )
        return True
```

**Step 3: Update Type Hints in Handlers**

```python
# Before
class MRWebhookHandler:
    def __init__(
        self,
        settings: Settings,
        gitlab_client: GitLabClient,
        queue_manager: QueueManager,  # Concrete type
    ) -> None: ...

# After
from gitlab_queue.core.protocols import QueueManagerProtocol

class MRWebhookHandler:
    def __init__(
        self,
        settings: Settings,
        gitlab_client: GitLabClient,
        queue_manager: QueueManagerProtocol,  # Protocol type
    ) -> None: ...
```

### 4.3 Example Migration: Webhook Handler Test

**Before (MagicMock):**
```python
def given_handler(self):
    self.queue_manager = MagicMock()
    self.queue_manager.add_to_queue = AsyncMock()
    self.queue_manager.remove_from_queue = AsyncMock(return_value=True)
```

**After (FakeQueueManager):**
```python
from scenarios.fakes.queue_manager import FakeQueueManager

def given_handler(self):
    self.queue_manager = FakeQueueManager()
    # No need to configure - it has real behavior!
```

### 4.4 Directory Structure

```
scenarios/fakes/
├── __init__.py
├── queue_manager.py      # FakeQueueManager
└── notifier.py           # FakeNotifier (if needed)

src/gitlab_queue/core/
├── protocols.py          # NEW: Protocol definitions
├── queue.py              # Existing QueueManager
└── ...
```

### 4.5 Full Inventory of MagicMock Usage

After comprehensive search, **51 files** use MagicMock/AsyncMock:

```
scenarios/
├── contexts/
│   ├── api_helpers.py                    # Mock factories
│   └── state_machine_helpers.py          # Mock factories
├── core/
│   ├── queue_manager/_helpers.py         # Mock database
│   └── state_machine/*.py                # 4 files
├── integration/
│   └── api/
│       ├── analytics/*.py                # 7 files - mock UnitOfWork
│       ├── auth/*.py                     # 1 file
│       ├── history/*.py                  # 6 files - mock UnitOfWork  
│       ├── queue/*.py                    # 6 files
│       └── websocket/*.py                # 8 files - mock WebSocket
├── unit/
│   ├── scheduler_sync.py                 # Mock gitlab_client, queue_manager
│   └── scheduler_shutdown.py
└── webhooks/
    ├── health/_helpers.py                # Mock factories
    ├── mr_webhook/_helpers.py            # Mock factories
    ├── mr_webhook/*.py                   # 2 files
    └── pipeline_webhook/*.py             # 8 files
```

### 4.6 Additional Protocols and Fakes Needed

The codebase has more MagicMock usage beyond QueueManager:

| Mock Factory | Location | Replacement |
|--------------|----------|-------------|
| `created_mock_settings()` | `api_helpers.py` | Real `Settings` with test values |
| `created_mock_database()` | `api_helpers.py` | Real `Database` with in-memory SQLite (already exists!) |
| `created_mock_gitlab_client()` | `api_helpers.py` | Real `GitLabClient` + `MockTransport` |
| `created_mock_queue_manager()` | `api_helpers.py` | `FakeQueueManager` |
| `created_mock_notifier()` | `api_helpers.py` | `FakeNotifier` (new) |
| `created_mock_circuit_breaker()` | `api_helpers.py` | Real `CircuitBreaker` with test config |
| `created_mock_retry_manager()` | `api_helpers.py` | `FakeRetryManager` (new) |
| `MagicMock(WebSocket)` | `websocket/*.py` | `FakeWebSocket` (new) |
| `MagicMock(UnitOfWork)` | `history/*.py`, `analytics/*.py` | `FakeUnitOfWork` or real with in-memory DB |
| `Mock(QueueItem)` | `scheduler_sync.py` | Real `QueueItem` instances |

**Additional Protocols Needed:**

```python
# src/gitlab_queue/core/protocols.py

class NotifierProtocol(Protocol):
    """Protocol for MR notification service."""
    
    async def notify(
        self,
        mr_iid: int,
        event: str,
        **context: Any,
    ) -> None: ...
    
    async def remove_queue_label(self, mr_iid: int) -> None: ...
    
    def build_pipeline_url(self, pipeline_id: int) -> str: ...


class RetryManagerProtocol(Protocol):
    """Protocol for webhook retry manager."""
    
    async def get_dlq_entries(self) -> list[Any]: ...
    
    async def get_dlq_stats(self) -> Any: ...


class WebSocketProtocol(Protocol):
    """Protocol for WebSocket connection (for testing broadcasts)."""
    
    async def send_json(self, data: dict) -> None: ...
    
    @property
    def client_state(self) -> Any: ...


class UnitOfWorkProtocol(Protocol):
    """Protocol for database unit of work pattern."""
    
    async def __aenter__(self) -> "UnitOfWorkProtocol": ...
    async def __aexit__(self, *args) -> None: ...
    
    @property
    def history(self) -> Any: ...  # HistoryRepository
```

**Additional Fakes:**

```
scenarios/fakes/
├── __init__.py
├── queue_manager.py      # FakeQueueManager
├── notifier.py           # FakeNotifier
├── retry_manager.py      # FakeRetryManager
├── websocket.py          # FakeWebSocket (records sent messages)
├── unit_of_work.py       # FakeUnitOfWork with FakeHistoryRepository
└── settings.py           # Test settings factory (real Settings, not Mock)
```

**FakeWebSocket Example:**

```python
@dataclass
class FakeWebSocket:
    """Fake WebSocket that records all sent messages."""
    
    sent_messages: list[dict] = field(default_factory=list)
    _state: str = "CONNECTED"
    
    async def send_json(self, data: dict) -> None:
        self.sent_messages.append(data)
    
    @property
    def client_state(self) -> Any:
        mock_state = type("ClientState", (), {"name": self._state})()
        return mock_state
    
    def disconnect(self) -> None:
        self._state = "DISCONNECTED"
```

**FakeUnitOfWork Example:**

```python
@dataclass 
class FakeHistoryRepository:
    """In-memory history repository."""
    
    _items: dict[int, Any] = field(default_factory=dict)
    
    async def get_by_iid(self, iid: int) -> Any:
        return self._items.get(iid)
    
    async def get_history(
        self,
        limit: int = 10,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Any:
        # Filter and paginate _items
        ...


@dataclass
class FakeUnitOfWork:
    """Fake UnitOfWork with in-memory repositories."""
    
    history: FakeHistoryRepository = field(default_factory=FakeHistoryRepository)
    
    async def __aenter__(self) -> "FakeUnitOfWork":
        return self
    
    async def __aexit__(self, *args) -> None:
        pass
```

**FakeNotifier Example:**

```python
@dataclass
class FakeNotifier:
    """In-memory fake notifier that records all notifications."""
    
    notifications: list[tuple[int, str, dict]] = field(default_factory=list)
    removed_labels: list[int] = field(default_factory=list)
    gitlab_url: str = "https://gitlab.example.com"
    project_id: int = 123
    
    async def notify(
        self,
        mr_iid: int,
        event: str,
        **context: Any,
    ) -> None:
        self.notifications.append((mr_iid, event, context))
    
    async def remove_queue_label(self, mr_iid: int) -> None:
        self.removed_labels.append(mr_iid)
    
    def build_pipeline_url(self, pipeline_id: int) -> str:
        return f"{self.gitlab_url}/project/{self.project_id}/-/pipelines/{pipeline_id}"
```

**Test Settings Factory (not Mock):**

```python
# scenarios/fakes/settings.py

def created_test_settings(
    *,
    jwt_secret: str = "test-secret-key-for-jwt-tokens-minimum-64-characters-long-here",
    gitlab_url: str = "https://gitlab.example.com",
    gitlab_project_id: int = 123,
    # ... other params
) -> Settings:
    """Create real Settings instance for testing.
    
    Unlike MagicMock, this creates a real Settings object with
    test-appropriate defaults. This ensures type safety and
    catches issues with Settings usage.
    """
    return Settings(
        gitlab_url=gitlab_url,
        gitlab_token="test-token",
        gitlab_project_id=gitlab_project_id,
        jwt_secret=jwt_secret,
        webhook_enabled=False,
        # ... etc
    )
```

### 4.7 Acceptance Criteria

- [ ] `QueueManagerProtocol` defined in `src/gitlab_queue/core/protocols.py`
- [ ] `NotifierProtocol` defined
- [ ] `RetryManagerProtocol` defined
- [ ] `WebSocketProtocol` defined
- [ ] `UnitOfWorkProtocol` defined
- [ ] `FakeQueueManager` implements full protocol
- [ ] `FakeNotifier` implements full protocol  
- [ ] `FakeRetryManager` implements full protocol
- [ ] `FakeWebSocket` implements full protocol
- [ ] `FakeUnitOfWork` implements full protocol
- [ ] `created_test_settings()` returns real `Settings`, not `MagicMock`
- [ ] All helper files migrated:
  - [ ] `scenarios/contexts/api_helpers.py`
  - [ ] `scenarios/contexts/state_machine_helpers.py`
  - [ ] `scenarios/core/queue_manager/_helpers.py`
  - [ ] `scenarios/webhooks/health/_helpers.py`
  - [ ] `scenarios/webhooks/mr_webhook/_helpers.py`
  - [ ] `scenarios/webhooks/pipeline_webhook/_helpers.py`
  - [ ] `scenarios/integration/api/history/_helpers.py`
- [ ] All 51 test files migrated from MagicMock to Fakes
- [ ] All fakes have their own test suites

---

## Phase 5: Remove JJ Dependency

### 5.1 Cleanup Tasks

- [ ] Delete `scenarios/mocks/gitlab/` directory
- [ ] Delete `scenarios/contexts/jj_gitlab_mock.py`
- [ ] Remove `jj` from `pyproject.toml` dependencies
- [ ] Remove `JJ_MOCK_URL` environment variable references
- [ ] Update CI/CD to not start JJ mock server

### 5.2 Documentation Updates

- [ ] Update `CLAUDE.md` testing section
- [ ] Update any README testing instructions
- [ ] Add examples to docstrings

---

## Benefits

| Benefit | Description |
|---------|-------------|
| No external dependencies | Tests don't require running mock server |
| Faster tests | No network overhead, pure in-memory mocking |
| Better isolation | Each test has its own transport instance |
| Deterministic | No race conditions with external mock server |
| Follows best practices | "Don't mock what you don't own" principle |
| Better error messages | Mock transport can report unregistered paths |
| **Clean Code compliance** | DIP, SRP, KIS principles followed |
| **Type safety** | Protocols provide compile-time checks |
| **Reduced API surface** | 50+ exports → ~15 focused exports |
| **No code duplication** | Single source of truth for each Fake |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Large refactoring scope | Migrate incrementally, keep JJ working during transition |
| Complex response sequences | `register_sequence()` method handles this |
| Regex path matching | Built into transport, same patterns as JJ |
| Request body assertions | Access via `transport.history` |

---

## Timeline Estimate

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase 1: GitLabClient transport injection | 1-2 hours | None |
| Phase 2: MockTransport factory | 3-4 hours | Phase 1 |
| Phase 3: Migrate tests to MockTransport | 8-12 hours | Phase 2 |
| Phase 4: Protocols + All Fakes (6 fakes, 7 helper files, 51 test files) | 12-16 hours | None (parallel with 1-3) |
| Phase 5: Remove JJ dependency + cleanup | 1-2 hours | Phase 3 + 4 complete |
| Phase 6: Clean Code refactoring (split files, remove duplication) | 2-4 hours | Phase 4 + 5 complete |

**Total: ~27-40 hours**

### Migration Statistics

- **Files with MagicMock/AsyncMock:** 51
- **Helper files to rewrite:** 7
- **Helper files to delete:** 2 (duplicates)
- **Fake implementations to create:** 6
- **Protocols to define:** 5
- **Files to delete:** ~15 (JJ mocks)
- **Backward compatibility aliases to remove:** 16
- **Export reduction:** 50+ → ~15

## Final State After Migration

After completing all phases, the testing architecture will be:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              TEST CODE                                        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │ GitLabClient    │  │ Settings        │  │ Database                     │  │
│  │ (REAL)          │  │ (REAL)          │  │ (REAL, in-memory SQLite)     │  │
│  └────────┬────────┘  └─────────────────┘  └──────────────────────────────┘  │
│           │                                                                   │
│           │ transport=                                                        │
│           │                                                                   │
│  ┌────────▼────────┐                                                         │
│  │ MockTransport   │                                                         │
│  │ (httpx builtin) │                                                         │
│  └─────────────────┘                                                         │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    FAKES (implement Protocols)                          │ │
│  │                                                                         │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │ │
│  │  │ FakeQueueManager│  │ FakeNotifier    │  │ FakeRetryManager        │  │ │
│  │  │ (in-memory)     │  │ (records calls) │  │ (in-memory DLQ)         │  │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│  NO MagicMock!   NO AsyncMock!   NO JJ server!   NO monkey-patching!         │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

### What's Eliminated

| Before | After |
|--------|-------|
| `MagicMock(Settings)` | Real `Settings` with test values |
| `MagicMock(GitLabClient)` | Real `GitLabClient` + `MockTransport` |
| `MagicMock(QueueManager)` | `FakeQueueManager` (implements Protocol) |
| `MagicMock(Notifier)` | `FakeNotifier` (implements Protocol) |
| `MagicMock(Database)` | Real `Database` with in-memory SQLite |
| `MagicMock(CircuitBreaker)` | Real `CircuitBreaker` with test config |
| `MagicMock(RetryManager)` | `FakeRetryManager` (implements Protocol) |
| `MagicMock(WebSocket)` | `FakeWebSocket` (implements Protocol) |
| `MagicMock(UnitOfWork)` | `FakeUnitOfWork` (implements Protocol) |
| `Mock(QueueItem)` | Real `QueueItem` instances |
| `AsyncMock` for methods | Gone - fakes have real async behavior |
| JJ remote mock server | Gone |
| Monkey-patching | Gone |

**Total: 51 files to migrate**

### What Remains

- **Real production classes** - Settings, GitLabClient, Database, CircuitBreaker
- **Dependency injection** - via constructor parameters  
- **Protocol-based interfaces** - for type safety and swappable implementations
- **In-memory fakes** - with real behavior, not just return value stubs
- **MockTransport** - httpx's official testing mechanism

### Files to Delete After Migration

```
scenarios/
├── contexts/
│   └── jj_gitlab_mock.py          # DELETE
└── mocks/
    └── gitlab/                    # DELETE entire directory
        ├── _base.py
        ├── mocked_gitlab_*.py
        └── ...
```

### Files to Rewrite (remove MagicMock)

```
scenarios/
├── contexts/
│   ├── api_helpers.py             # REWRITE (see Phase 6 for split)
│   └── state_machine_helpers.py   # DELETE (duplicates api_helpers.py)
├── core/
│   └── queue_manager/_helpers.py  # REWRITE
├── integration/
│   └── api/
│       └── history/_helpers.py    # REWRITE
└── webhooks/
    ├── health/_helpers.py         # REWRITE
    ├── mr_webhook/_helpers.py     # REWRITE
    └── pipeline_webhook/_helpers.py # REWRITE
```

---

## Phase 6: Clean Code Refactoring

Based on Clean Code analysis, additional refactoring is needed after Fakes are implemented.

### 6.1 Split `api_helpers.py` (652 lines → multiple modules)

Current `api_helpers.py` violates SRP - it handles 6+ different domains. Split into:

```
scenarios/contexts/
├── __init__.py                    # Minimal re-exports
├── sqlite_client.py               # KEEP (already clean)
├── gitlab_client_factory.py       # KEEP (update for MockTransport)
└── jwt_helpers.py                 # EXTRACT from api_helpers.py

scenarios/fakes/
├── __init__.py
├── queue_manager.py               # FakeQueueManager
├── notifier.py                    # FakeNotifier  
├── retry_manager.py               # FakeRetryManager
├── websocket.py                   # FakeWebSocket
├── unit_of_work.py                # FakeUnitOfWork
├── app_state.py                   # created_webhook_state(), created_test_app()
└── test_data.py                   # created_test_queue_item(), created_test_history_items()
```

### 6.2 Delete Duplicated Files

| File | Action | Reason |
|------|--------|--------|
| `state_machine_helpers.py` | DELETE | Duplicates `create_mock_notifier()`, `create_mock_queue_manager()` from api_helpers |
| `webhooks/health/_helpers.py` | DELETE | Duplicates mock factories from api_helpers |

### 6.3 Remove Backward Compatibility Aliases

After all tests are migrated, remove duplicate exports:

```python
# BEFORE (api_helpers.py)
def created_mock_settings(...): ...
create_mock_settings = created_mock_settings  # DELETE this alias

# AFTER
def created_test_settings(...) -> Settings:  # Returns REAL Settings
    ...
```

**Aliases to remove:** 16 functions × 2 names = 32 exports → 16 exports

### 6.4 Simplify `__init__.py` Exports

Current `__init__.py` exports 50+ names. After refactoring:

```python
# scenarios/contexts/__init__.py - AFTER
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.contexts.gitlab_client_factory import created_test_client, created_test_settings
from scenarios.contexts.jwt_helpers import created_test_jwt, created_expired_jwt

from scenarios.fakes import (
    FakeQueueManager,
    FakeNotifier,
    FakeRetryManager,
    FakeWebSocket,
    FakeUnitOfWork,
)

__all__ = [
    # Real objects
    "initialized_test_database",
    "created_test_client",
    "created_test_settings",
    "created_test_jwt",
    "created_expired_jwt",
    # Fakes
    "FakeQueueManager",
    "FakeNotifier", 
    "FakeRetryManager",
    "FakeWebSocket",
    "FakeUnitOfWork",
]
# ~12 exports instead of 50+
```

### 6.5 Acceptance Criteria

- [ ] `api_helpers.py` split into domain-specific modules
- [ ] `state_machine_helpers.py` deleted
- [ ] `webhooks/health/_helpers.py` deleted (use shared fakes)
- [ ] All backward compatibility aliases removed
- [ ] `__init__.py` exports reduced from 50+ to ~15
- [ ] No code duplication between helper files
- [ ] Each module has single responsibility

### New Files Created

```
src/gitlab_queue/core/
└── protocols.py                   # NEW: Protocol definitions

scenarios/
├── fakes/                         # NEW: Fake implementations
│   ├── __init__.py
│   ├── queue_manager.py           # FakeQueueManager
│   ├── notifier.py                # FakeNotifier
│   ├── retry_manager.py           # FakeRetryManager
│   ├── websocket.py               # FakeWebSocket
│   ├── unit_of_work.py            # FakeUnitOfWork + FakeHistoryRepository
│   └── settings.py                # Real Settings factory
└── transports/                    # NEW: MockTransport utilities
    ├── __init__.py
    ├── gitlab_mock_transport.py
    └── responses/
        ├── mr_responses.py
        ├── pipeline_responses.py
        └── ...
```

---

## References

- [Don't mock Python's HTTPX](https://www.b-list.org/weblog/2023/dec/08/mock-python-httpx/) - James Bennett
- [HTTPX Mock Transports](https://www.python-httpx.org/advanced/#mock-transports) - Official docs
- [What to Mock in 5 Minutes](https://hynek.me/articles/what-to-mock-in-5-mins/) - Hynek Schlawack
