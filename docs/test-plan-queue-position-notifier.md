# Test Plan: QueuePositionNotifier

## Overview

Unit tests for `QueuePositionNotifier` class (`backend/src/gitlab_queue/core/queue_position_notifier.py`) and related handler integration.

## Test Location

```text
backend/scenarios/unit/
├── queue_position_notifier/         # QueuePositionNotifier unit tests
│   ├── __init__.py
│   ├── _helpers.py
│   ├── notify_initial_position/
│   │   ├── __init__.py
│   │   ├── sends_notification_with_correct_position.py
│   │   ├── uses_queued_at_from_queue_item.py
│   │   ├── calculates_estimated_time_for_various_positions.py
│   │   └── does_not_notify_when_mr_not_in_queue.py
│   ├── capture_queue_positions/
│   │   ├── __init__.py
│   │   ├── captures_only_queued_state_mrs.py
│   │   ├── excludes_non_queued_states.py
│   │   ├── returns_correct_1_indexed_positions.py
│   │   └── returns_empty_dict_for_empty_queue.py
│   ├── notify_position_changes/     # _notify_position_changes internal method tests
│   │   ├── __init__.py
│   │   ├── notifies_mrs_with_changed_position.py
│   │   ├── returns_correct_notified_count.py
│   │   ├── skips_excluded_mr_iid.py
│   │   ├── skips_mrs_not_in_positions_before.py
│   │   ├── skips_non_queued_states.py
│   │   └── skips_unchanged_positions.py
│   ├── notify_affected_mrs_after_completion/
│   │   ├── __init__.py
│   │   └── notifies_affected_mrs_after_mr_completes.py
│   └── notify_affected_mrs_after_hotfix_added/
│       ├── __init__.py
│       └── notifies_with_hotfix_context.py
│
└── handlers/                        # Handler integration tests
    ├── __init__.py
    └── notify_position_after_add/   # MRWebhookHandler notification tests
        ├── __init__.py
        ├── catches_exceptions_and_logs_warning.py
        ├── calls_hotfix_notification_when_is_hotfix.py
        └── skips_hotfix_notification_when_not_hotfix.py
```

## Test Scenarios

### 1. `notify_initial_position`

#### 1.1 Sends notification with correct position

- **Given**: Queue with 3 MRs, target MR at position 2
- **When**: `notify_initial_position(mr_iid)` called
- **Then**: `notifier.notify()` called with:
  - `template="queued"`
  - `position=2`
  - `total=3`
  - `estimated_minutes=30` (2 * 15)

#### 1.2 Uses queued_at from QueueItem

- **Given**: Queue with MR that has specific `queued_at` timestamp
- **When**: `notify_initial_position(mr_iid)` called
- **Then**: `notifier.notify()` called with `queued_at` matching the QueueItem's value (not `datetime.now()`)

#### 1.3 Does not notify when MR not in queue

- **Given**: Empty queue
- **When**: `notify_initial_position(123)` called
- **Then**:
  - `notifier.notify()` NOT called
  - Warning logged with `mr_iid=123`

### 2. `capture_queue_positions`

#### 2.1 Captures only queued state MRs

- **Given**: Queue with:
  - MR1 (state="queued", position 1)
  - MR2 (state="rebasing", position 2)
  - MR3 (state="queued", position 3)
- **When**: `capture_queue_positions()` called
- **Then**: Returns `{MR1: 1, MR3: 3}` (MR2 excluded)

#### 2.2 Returns correct 1-indexed positions

- **Given**: Queue with 3 MRs all in "queued" state
- **When**: `capture_queue_positions()` called
- **Then**: Returns `{MR1: 1, MR2: 2, MR3: 3}`

### 3. `notify_affected_mrs_after_completion`

#### 3.1 Notifies MRs with changed position

- **Given**:
  - `positions_before = {MR1: 2, MR2: 3}`
  - Current queue: MR1 at position 1, MR2 at position 2
- **When**: `notify_affected_mrs_after_completion(completed_mr_iid, positions_before)` called
- **Then**: `notifier.notify()` called for MR1 and MR2 with:
  - `template="position_changed"`
  - Correct `old_position` and `position` values

#### 3.2 Skips excluded MR

- **Given**:
  - `positions_before = {MR1: 1, MR2: 2}`
  - `excluded_mr_iid = MR1`
- **When**: `notify_affected_mrs_after_completion(MR1, positions_before)` called
- **Then**: `notifier.notify()` NOT called for MR1

#### 3.3 Skips unchanged positions

- **Given**:
  - `positions_before = {MR1: 1}`
  - Current queue: MR1 still at position 1
- **When**: `notify_affected_mrs_after_completion(other_mr, positions_before)` called
- **Then**: `notifier.notify()` NOT called for MR1

#### 3.4 Skips non-queued states

- **Given**:
  - `positions_before = {MR1: 2}`
  - Current queue: MR1 at position 1 but state="rebasing"
- **When**: `notify_affected_mrs_after_completion(other_mr, positions_before)` called
- **Then**: `notifier.notify()` NOT called for MR1

### 4. `notify_affected_mrs_after_hotfix_added`

#### 4.1 Notifies with hotfix context

- **Given**:
  - Hotfix MR (iid=100) added to front of queue
  - `positions_before = {MR1: 1, MR2: 2}` (before hotfix)
  - Current queue: Hotfix at position 1, MR1 at position 2, MR2 at position 3
- **When**: `notify_affected_mrs_after_hotfix_added(hotfix_mr_iid=100, positions_before)` called
- **Then**:
  - `notifier.notify()` called for MR1 and MR2 (NOT for hotfix MR)
  - Each call has `template="position_changed"`
  - Each call includes `position`, `old_position`, `total`, `estimated_minutes`
  - MR1: `old_position=1`, `position=2`
  - MR2: `old_position=2`, `position=3`
  - Log message includes "due to hotfix" context with `hotfix_mr_iid=100`

## Handler Integration Tests

### 5. `_notify_position_after_add` (in `MRWebhookHandler`)

Location: `backend/scenarios/unit/handlers/`

#### 5.1 Catches exceptions and logs warning

- **Given**: `position_notifier.notify_initial_position()` raises Exception
- **When**: `_notify_position_after_add(mr_iid, is_hotfix, positions_before)` called
- **Then**:
  - Exception NOT propagated
  - Warning logged with `mr_iid` and error message

#### 5.2 Calls hotfix notification when is_hotfix=True

- **Given**: `is_hotfix=True`, `positions_before` has data
- **When**: `_notify_position_after_add(mr_iid, True, positions_before)` called
- **Then**: Both `notify_initial_position()` and `notify_affected_mrs_after_hotfix_added()` called

#### 5.3 Skips hotfix notification when is_hotfix=False

- **Given**: `is_hotfix=False`
- **When**: `_notify_position_after_add(mr_iid, False, {})` called
- **Then**: Only `notify_initial_position()` called

## Test Helpers (`_helpers.py`)

> **Note**: The code below is illustrative. See
> `backend/scenarios/unit/queue_position_notifier/_helpers.py` for the
> authoritative implementation.

```python
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, UTC
from dataclasses import dataclass

from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier


def create_mock_notifier() -> MagicMock:
    """Create mock MRNotifier."""
    notifier = MagicMock()
    notifier.notify = AsyncMock()
    return notifier


def create_mock_queue_manager(queue_items: list | None = None) -> MagicMock:
    """Create mock QueueManager with configurable queue."""
    manager = MagicMock()
    manager.get_active_queue = AsyncMock(return_value=queue_items or [])
    return manager


@dataclass
class MockQueueItem:
    """Mock QueueItem for testing."""
    mr_iid: int
    state: str = "queued"
    queued_at: datetime | None = None

    def __post_init__(self):
        if self.queued_at is None:
            self.queued_at = datetime.now(UTC)


def create_position_notifier(
    notifier: MagicMock | None = None,
    queue_manager: MagicMock | None = None,
) -> QueuePositionNotifier:
    """Create QueuePositionNotifier with mocks."""
    return QueuePositionNotifier(
        notifier=notifier or create_mock_notifier(),
        queue_manager=queue_manager or create_mock_queue_manager(),
    )
```

## Priority

1. **High**: Scenarios 1.1, 1.3, 3.1, 3.2 (core functionality)
2. **Medium**: Scenarios 2.1, 3.3, 3.4, 5.1 (edge cases)
3. **Low**: Scenarios 1.2, 2.2, 4.1, 5.2, 5.3 (additional coverage)

## Estimated Effort

- Helper setup: 30 min
- High priority tests: 2 hours
- Medium priority tests: 1.5 hours
- Low priority tests: 1 hour

### Total: ~5 hours
