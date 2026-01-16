# Plan for Adapting Tests to Vedro Codestyle

This document contains a comprehensive plan for adapting the existing test suite to comply with the Vedro codestyle guidelines defined in:
- `CommonCodeStyles.md` - General rules for all projects
- `BackendCodeStyles.md` - Backend-specific rules

## Current State

| Category | Files | Scenarios |
|----------|-------|-----------|
| **Class style (need to split)** | 28 | 217 |
| **Functional style (need to convert)** | 15 | 87 |
| **TOTAL** | 43 | **304** |

## Completed Work

### Pilot Phase
- [x] Updated `pyproject.toml`: `line-length = 100` → `line-length = 120`
- [x] Converted `processor_happy_path.py` (2 scenarios) to class style
- [x] Split `queue_add_mr.py` (4 scenarios) into separate files
- [x] All 350 tests passing

### Phase 2: Split Files with Multiple Class Scenarios (DONE)
- [x] Split `core/test_queue_manager.py` (11 scenarios) → `core/queue_manager/*.py`
- [x] Split `integration/api_auth.py` (16 scenarios) → `integration/api/auth/*.py`
- [x] Split `integration/api_websocket.py` (14 scenarios) → `integration/api/websocket/*.py`
- [x] Split `config/test_settings_validation.py` (14 scenarios) → `config/settings_validation/*.py`
- [x] Split `webhooks/test_mr_webhook_handler.py` (13 scenarios) → `webhooks/mr_webhook/*.py`
- [x] Split `config/test_secret.py` (12 scenarios) → `config/secret/*.py`
- [x] Split `models/test_events.py` (11 scenarios) → `models/events/*.py`
- [x] Split `unit/gitlab_client_errors.py` (11 scenarios) → `unit/gitlab_client/errors/*.py`
- [x] Split `integration/api_analytics.py` (10 scenarios) → `integration/api/analytics/*.py`
- [x] Split `integration/api_queue.py` (10 scenarios) → `integration/api/queue/*.py`
- [x] Split `webhooks/test_pipeline_webhook_handler.py` (9 scenarios) → `webhooks/pipeline_webhook/*.py`
- [x] Split `unit/gitlab_client_comments.py` (8 scenarios) → `unit/gitlab_client/comments/*.py`
- [x] Split `unit/gitlab_client_rebase.py` (8 scenarios) → `unit/gitlab_client/rebase/*.py`
- [x] Split `integration/api_history.py` (8 scenarios) → `integration/api/history/*.py`
- [x] Split `models/test_mr.py` (7 scenarios) → `models/mr/*.py`
- [x] Split `models/test_pipeline.py` (7 scenarios) → `models/pipeline/*.py`
- [x] Split `unit/gitlab_client_pipelines.py` (7 scenarios) → `unit/gitlab_client/pipelines/*.py`
- [x] Split `webhooks/test_health_endpoints.py` (6 scenarios) → `webhooks/health/*.py`
- [x] Split `unit/gitlab_client_get_mr.py` (4 scenarios) → `unit/gitlab_client/get_mr/*.py`
- [x] Split `unit/gitlab_client_list_mrs.py` (4 scenarios) → `unit/gitlab_client/list_mrs/*.py`
- [x] Split `unit/gitlab_client_merge.py` (4 scenarios) → `unit/gitlab_client/merge/*.py`
- [x] Split `unit/queue_fifo_order.py` (4 scenarios) → `unit/queue/fifo_order/*.py`
- [x] Split `unit/queue_hotfix_priority.py` (4 scenarios) → `unit/queue/hotfix_priority/*.py`
- [x] Split `unit/queue_remove_mr.py` (4 scenarios) → `unit/queue/remove_mr/*.py`
- [x] Split `models/test_queue_item.py` (3 scenarios) → `models/queue_item/*.py`
- [x] All 350 tests passing (including random order)

### Phase 3: Rename Contexts and Mocks (DONE)
- [x] Verified mocks already use `mocked_` prefix in `jj_gitlab_mock.py`
- [x] Verified `@vedro.context` decorators are present on all context managers
- [x] Updated all scenario imports to use new naming convention:
  - `test_database` → `initialized_test_database` (21 files)
  - `create_test_app` → `created_test_app` (many files)
  - `create_test_jwt` → `created_test_jwt` (many files)
  - `create_test_settings` → `created_test_settings` (5 files)
  - `create_mock_settings` → `created_mock_settings` (many files)
- [x] Updated local `_helpers.py` files with aliases for backward compatibility
- [x] All 350 tests passing

---

## Phase 1: Convert Functional Style Scenarios to Class Style

**15 files → 87 new files**

All files using `@scenario()` decorator must be converted to class-based `class Scenario(vedro.Scenario)`.

### Conversion Pattern

**Before (functional style):**
```python
from vedro import given, scenario, then, when

@scenario()
async def process_mr_successfully():
    with given("MR in queue"):
        db = Database(...)
        await db.initialize()
        
    with when("processor runs"):
        result = await processor.process()
        
    with then("MR is merged"):
        assert result == ProcessingResult.SUCCESS
```

**After (class style):**
```python
import vedro

class Scenario(vedro.Scenario):
    subject = "process mr successfully"

    async def given_mr_in_queue(self):
        self.db = Database(...)
        await self.db.initialize()
    
    async def when_processor_runs(self):
        self.result = await self.processor.process()
    
    async def then_mr_should_be_merged(self):
        assert self.result == ProcessingResult.SUCCESS
```

### Files to Convert (Priority Order)

| File | Scenarios | Priority | New Location |
|------|-----------|----------|--------------|
| `unit/rate_limit.py` | 19 | High | `unit/rate_limit/*.py` |
| `unit/circuit_breaker.py` | 16 | High | `unit/circuit_breaker/*.py` |
| `unit/scheduler_sync.py` | 6 | Medium | `unit/scheduler/sync/*.py` |
| `unit/scheduler_shutdown.py` | 5 | Medium | `unit/scheduler/shutdown/*.py` |
| `unit/processor_shutdown.py` | 5 | Medium | `unit/processor/shutdown/*.py` |
| `integration/webhook_flow.py` | 5 | Medium | `integration/webhook/flow/*.py` |
| `integration/scheduler_integration.py` | 4 | Medium | `integration/scheduler/*.py` |
| `integration/webhook_pipeline.py` | 4 | Medium | `integration/webhook/pipeline/*.py` |
| `integration/full_flow_concurrent.py` | 4 | Medium | `integration/full_flow/concurrent/*.py` |
| `unit/processor_timeout.py` | 4 | Medium | `unit/processor/timeout/*.py` |
| `unit/processor_conflict.py` | 3 | Low | `unit/processor/conflict/*.py` |
| `unit/processor_pipeline_failure.py` | 3 | Low | `unit/processor/pipeline_failure/*.py` |
| `integration/full_flow_restart.py` | 3 | Low | `integration/full_flow/restart/*.py` |
| `integration/full_flow_hotfix.py` | 2 | Low | `integration/full_flow/hotfix/*.py` |
| `integration/full_flow.py` | 1 | Low | `integration/full_flow/failures_and_recovery.py` |
| `integration/full_flow_multiple_mrs.py` | 1 | Low | `integration/full_flow/multiple_mrs.py` |
| `unit/processor_pipeline_non_actionable.py` | 1 | Low | `unit/processor/pipeline_non_actionable.py` |

### Key Rules for Conversion

1. **Class name:** Always `class Scenario(vedro.Scenario)`, never `Scenario__something`
2. **Subject:** Lowercase, reflects the action from `when_` step
3. **Step naming:**
   - `given_` - Past participle (e.g., `given_mr_in_queue`, `given_database_initialized`)
   - `when_` - Present tense (e.g., `when_processor_runs`, `when_mr_is_added`)
   - `then_/and_` - Present/future (e.g., `then_it_should_return_success`)
4. **One file = one scenario**
5. **Store state in `self`** instead of local variables
6. **No helper functions or constants in test files** - move them to `contexts/helpers.py` or `library/`

---

## Phase 2: Split Files with Multiple Class Scenarios

**28 files → 217 new files**

Each file containing multiple `Scenario__*` classes must be split so that each file contains exactly one `class Scenario`.

### Large Files (>10 scenarios)

| File | Scenarios | New Structure |
|------|-----------|---------------|
| `core/test_state_machine.py` | 44 | `core/state_machine/*.py` |
| `integration/api_auth.py` | 16 | `integration/api/auth/*.py` |
| `integration/api_websocket.py` | 14 | `integration/api/websocket/*.py` |
| `config/test_settings_validation.py` | 14 | `config/settings_validation/*.py` |
| `webhooks/test_mr_webhook_handler.py` | 13 | `webhooks/mr_webhook/*.py` |
| `config/test_secret.py` | 12 | `config/secret/*.py` |
| `core/test_queue_manager.py` | 11 | `core/queue_manager/*.py` |
| `models/test_events.py` | 11 | `models/events/*.py` |
| `unit/gitlab_client_errors.py` | 11 | `unit/gitlab_client/errors/*.py` |
| `integration/api_analytics.py` | 10 | `integration/api/analytics/*.py` |
| `integration/api_queue.py` | 10 | `integration/api/queue/*.py` |

### Medium Files (4-10 scenarios)

| File | Scenarios | New Structure |
|------|-----------|---------------|
| `webhooks/test_pipeline_webhook_handler.py` | 9 | `webhooks/pipeline_webhook/*.py` |
| `unit/gitlab_client_comments.py` | 8 | `unit/gitlab_client/comments/*.py` |
| `unit/gitlab_client_rebase.py` | 8 | `unit/gitlab_client/rebase/*.py` |
| `integration/api_history.py` | 8 | `integration/api/history/*.py` |
| `models/test_mr.py` | 7 | `models/mr/*.py` |
| `models/test_pipeline.py` | 7 | `models/pipeline/*.py` |
| `unit/gitlab_client_pipelines.py` | 7 | `unit/gitlab_client/pipelines/*.py` |
| `webhooks/test_health_endpoints.py` | 6 | `webhooks/health/*.py` |
| `unit/gitlab_client_get_mr.py` | 4 | `unit/gitlab_client/get_mr/*.py` |
| `unit/gitlab_client_list_mrs.py` | 4 | `unit/gitlab_client/list_mrs/*.py` |
| `unit/gitlab_client_merge.py` | 4 | `unit/gitlab_client/merge/*.py` |
| `unit/queue_fifo_order.py` | 4 | `unit/queue/fifo_order/*.py` |
| `unit/queue_hotfix_priority.py` | 4 | `unit/queue/hotfix_priority/*.py` |
| `unit/queue_remove_mr.py` | 4 | `unit/queue/remove_mr/*.py` |

### Small Files (≤3 scenarios)

| File | Scenarios | New Structure |
|------|-----------|---------------|
| `models/test_queue_item.py` | 3 | `models/queue_item/*.py` |

### Splitting Pattern

**Before (multiple classes in one file):**
```python
# queue_add_mr.py
class Scenario__add_mr_to_empty_queue(vedro.Scenario):
    subject = "add MR to empty queue"
    ...

class Scenario__add_mr_to_non_empty_queue(vedro.Scenario):
    subject = "add MR to non-empty queue"
    ...
```

**After (one class per file):**
```python
# queue/add_mr/add_mr_to_empty_queue.py
class Scenario(vedro.Scenario):
    subject = "add mr to empty queue"
    ...

# queue/add_mr/add_mr_to_non_empty_queue.py
class Scenario(vedro.Scenario):
    subject = "add mr to non-empty queue"
    ...
```

### File Naming Convention

- File name should match the scenario subject (snake_case)
- Remove `test_` prefix from directory names
- Example: `Scenario__add_mr_to_empty_queue` → `add_mr_to_empty_queue.py`

---

## Phase 3: Rename Contexts and Mocks (DONE)

### 3.1 Rename Mocks (Already Done)

**File:** `contexts/jj_gitlab_mock.py`

All mock functions should use `mocked_` prefix (not `mock_`):

| Current Name | New Name |
|--------------|----------|
| `mock_gitlab_get_mr` | `mocked_gitlab_get_mr` |
| `mock_gitlab_list_mrs` | `mocked_gitlab_list_mrs` |
| `mock_gitlab_rebase` | `mocked_gitlab_rebase` |
| `mock_gitlab_merge` | `mocked_gitlab_merge` |
| `mock_gitlab_pipeline` | `mocked_gitlab_pipeline` |
| `mock_gitlab_mr_pipelines` | `mocked_gitlab_mr_pipelines` |
| `mock_gitlab_add_comment` | `mocked_gitlab_add_comment` |
| `mock_gitlab_update_comment` | `mocked_gitlab_update_comment` |
| `mock_gitlab_rate_limit` | `mocked_gitlab_rate_limit` |
| `mock_gitlab_get_notes` | `mocked_gitlab_get_notes` |
| `mock_gitlab_get_conflicts` | `mocked_gitlab_get_conflicts` |
| `mock_gitlab_retry_job` | `mocked_gitlab_retry_job` |
| `mock_gitlab_pipeline_jobs` | `mocked_gitlab_pipeline_jobs` |

### 3.2 Add `@vedro.context` Decorator and Rename Contexts (DONE)

**Files:**
- `contexts/api_helpers.py`
- `contexts/sqlite_client.py`
- `contexts/gitlab_client_factory.py`

**Requirements:**
1. Add `@vedro.context` decorator
2. Rename to past tense (participle)
3. Add guaranteeing assert statements

**Example transformation:**

```python
# Before
@asynccontextmanager
async def test_database() -> AsyncIterator[Database]:
    db = Database(database_url="sqlite+aiosqlite:///:memory:")
    await db.initialize()
    yield db

# After
@vedro.context
@asynccontextmanager
async def initialized_test_database() -> AsyncIterator[Database]:
    """
    Creates and initializes in-memory test database.
    
    :return: Initialized Database instance
    """
    db = Database(database_url="sqlite+aiosqlite:///:memory:")
    await db.initialize()
    health = await db.health_check()
    assert health.connected, "Database should be connected"
    yield db
```

**Renaming table:**

| Current Name | New Name |
|--------------|----------|
| `test_database()` | `initialized_test_database()` |
| `create_test_app()` | `created_test_app()` |
| `create_test_jwt()` | `created_test_jwt()` |
| `create_mock_settings()` | `created_mock_settings()` |
| `create_mock_database()` | `created_mock_database()` |
| `create_mock_gitlab_client()` | `created_mock_gitlab_client()` |
| `create_mock_queue_manager()` | `created_mock_queue_manager()` |
| `create_test_queue_item()` | `created_test_queue_item()` |

### 3.3 Export Contexts via `__init__.py` (DONE)

Update `contexts/__init__.py` to export all contexts:

```python
from scenarios.contexts.api_helpers import (
    created_mock_settings,
    created_test_app,
    created_test_jwt,
    # ... all other contexts
)
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.contexts.jj_gitlab_mock import (
    mocked_gitlab_get_mr,
    mocked_gitlab_rebase,
    # ... all other mocks
)

__all__ = [
    "created_mock_settings",
    "created_test_app",
    # ... etc
]
```

---

## Phase 4: Update Subject for Negative Scenarios (DONE)

### Negative Scenario Naming Rules

- **Business-negative scenarios** (expecting error): Use `try to` prefix
- **Valid logic with empty result**: Use `do not`, `get no`, `get empty`

### Updated Scenarios (35 total)

#### API Auth Scenarios (10 files)
- [x] `me_rejects_invalid_token.py` → "try to get current user with invalid token"
- [x] `me_rejects_expired_token.py` → "try to get current user with expired token"
- [x] `me_rejects_missing_token.py` → "try to get current user without authorization header"
- [x] `me_rejects_malformed_header.py` → "try to get current user with malformed authorization header"
- [x] `middleware_rejects_wrong_auth_scheme.py` → "try to access protected route with non-bearer auth scheme"
- [x] `middleware_blocks_protected_routes.py` → "try to access protected route without token"
- [x] `callback_rejects_invalid_state.py` → "try to exchange code with mismatched state parameter"
- [x] `callback_rejects_missing_state.py` → "try to exchange code without state parameter"
- [x] `callback_rejects_missing_code.py` → "try to exchange token without authorization code"
- [x] `login_fails_when_oauth_not_configured.py` → "try to login when oauth is not configured"

#### API Queue/History 404 Scenarios (2 files)
- [x] `queue_item_endpoint_returns_404_for_non_existent_mr.py` → "try to get queue item for non-existent mr"
- [x] `history_item_endpoint_returns_404_for_non_existent_mr.py` → "try to get history item for non-existent mr"

#### WebSocket Rejection Scenarios (3 files)
- [x] `websocket_rejects_invalid_token.py` → "try to connect websocket with invalid token"
- [x] `websocket_rejects_expired_token.py` → "try to connect websocket with expired token"
- [x] `websocket_rejects_missing_token.py` → "try to connect websocket without token"

#### GitLab Client Error Scenarios (8 files)
- [x] `404_raises_not_found_error.py` → "try to get mr when gitlab returns 404"
- [x] `409_raises_conflict_error.py` → "try to get mr when gitlab returns 409"
- [x] `500_raises_server_error.py` → "try to get mr when gitlab returns 500"
- [x] `503_raises_server_error.py` → "try to get mr when gitlab returns 503"
- [x] `rebase_mr_raises_gitlab_conflict_error_on_409.py` → "try to rebase mr when gitlab returns 409"
- [x] `get_mr_raises_gitlab_not_found_error_on_404.py` → "try to get mr when mr not found"
- [x] `merge_mr_raises_gitlabconflicterror_when_merge_status_is_unchecked.py` → "try to merge mr when merge status is unchecked"
- [x] `merge_mr_raises_gitlabconflicterror_when_mr_is_not_mergeable.py` → "try to merge mr when mr is not mergeable"

#### Config Validation Scenarios (11 files)
- [x] `jwt_secret_too_short.py` → "try to validate settings with short jwt secret"
- [x] `zero_poll_interval.py` → "try to validate settings with zero poll interval"
- [x] `negative_project_id.py` → "try to validate settings with negative project id"
- [x] `negative_retry_count.py` → "try to validate settings with negative retry count"
- [x] `negative_pipeline_timeout.py` → "try to validate settings with negative pipeline timeout"
- [x] `invalid_gitlab_url.py` → "try to validate settings with invalid gitlab url"
- [x] `invalid_webhook_port.py` → "try to validate settings with invalid webhook port"
- [x] `invalid_cors_origin_protocol.py` → "try to validate settings with invalid cors origin protocol"
- [x] `wildcard_cors_origin.py` → "try to validate settings with wildcard cors origin"
- [x] `webhook_enabled_without_secret.py` → "try to validate settings with webhook enabled without secret"
- [x] `webhook_retry_delays_invalid.py` → "try to validate settings with max delay less than base delay"

#### Secret Class Scenarios (2 files)
- [x] `secret_attributes_cannot_be_deleted.py` → "try to delete secret attribute"
- [x] `secret_blocks_direct_access_to_secret_value.py` → "try to access secret value directly"

- [x] All 350 tests passing (including random order)

---

## Phase 5: Create Status Code Schemas (DONE)

- [x] Created `scenarios/schemas/status_code.py` with all HTTP status schemas
- [x] Created `scenarios/schemas/__init__.py` with exports
- [x] Added `d42>=1.12` to dev dependencies in `pyproject.toml`
- [x] Updated 59 test files to use status code schemas instead of magic numbers
- [x] All 350 tests passing (including random order)

### Create `scenarios/schemas/status_code.py`

```python
"""HTTP status code schemas for test assertions."""

from http import HTTPStatus

from d42 import schema

OkStatusSchema = schema.int(HTTPStatus.OK)
CreatedStatusSchema = schema.int(HTTPStatus.CREATED)
AcceptedStatusSchema = schema.int(HTTPStatus.ACCEPTED)
NoContentStatusSchema = schema.int(HTTPStatus.NO_CONTENT)
BadRequestStatusSchema = schema.int(HTTPStatus.BAD_REQUEST)
UnauthorizedStatusSchema = schema.int(HTTPStatus.UNAUTHORIZED)
ForbiddenStatusSchema = schema.int(HTTPStatus.FORBIDDEN)
NotFoundStatusSchema = schema.int(HTTPStatus.NOT_FOUND)
ConflictStatusSchema = schema.int(HTTPStatus.CONFLICT)
UnprocessableEntityStatusSchema = schema.int(HTTPStatus.UNPROCESSABLE_ENTITY)
InternalServerErrorStatusSchema = schema.int(HTTPStatus.INTERNAL_SERVER_ERROR)
ServiceUnavailableStatusSchema = schema.int(HTTPStatus.SERVICE_UNAVAILABLE)

__all__ = [
    "OkStatusSchema",
    "CreatedStatusSchema",
    "AcceptedStatusSchema",
    "NoContentStatusSchema",
    "BadRequestStatusSchema",
    "UnauthorizedStatusSchema",
    "ForbiddenStatusSchema",
    "NotFoundStatusSchema",
    "ConflictStatusSchema",
    "UnprocessableEntityStatusSchema",
    "InternalServerErrorStatusSchema",
    "ServiceUnavailableStatusSchema",
]
```

### Usage in Tests

**Before:**
```python
def then_it_should_return_success(self):
    assert self.response.status_code == 200
```

**After:**
```python
from scenarios.schemas.status_code import OkStatusSchema

def then_it_should_return_success(self):
    assert self.response.status_code == OkStatusSchema
```

---

## Phase 6: Restructure Mocks Directory (DONE)

- [x] Created `scenarios/mocks/` directory structure
- [x] Created `scenarios/mocks/gitlab/_base.py` with JJ_MOCK_URL and get_mock_url()
- [x] Created `scenarios/mocks/gitlab/mocked_gitlab_get_mr.py`
- [x] Created `scenarios/mocks/gitlab/mocked_gitlab_list_mrs.py`
- [x] Created `scenarios/mocks/gitlab/mocked_gitlab_rebase.py`
- [x] Created `scenarios/mocks/gitlab/mocked_gitlab_merge.py`
- [x] Created `scenarios/mocks/gitlab/mocked_gitlab_pipelines.py` (pipeline + mr_pipelines)
- [x] Created `scenarios/mocks/gitlab/mocked_gitlab_comments.py` (add_comment + update_comment)
- [x] Created `scenarios/mocks/gitlab/mocked_gitlab_notes.py`
- [x] Created `scenarios/mocks/gitlab/mocked_gitlab_conflicts.py`
- [x] Created `scenarios/mocks/gitlab/mocked_gitlab_jobs.py` (retry_job + pipeline_jobs)
- [x] Created `scenarios/mocks/gitlab/mocked_gitlab_rate_limit.py`
- [x] Updated `contexts/jj_gitlab_mock.py` to re-export from mocks/ for backward compatibility
- [x] All 350 tests passing (including random order)

### Final Structure
```
scenarios/
├── mocks/
│   ├── __init__.py
│   └── gitlab/
│       ├── __init__.py
│       ├── _base.py                     # JJ_MOCK_URL, get_mock_url()
│       ├── mocked_gitlab_get_mr.py      # GET /merge_requests/:iid
│       ├── mocked_gitlab_list_mrs.py    # GET /merge_requests
│       ├── mocked_gitlab_rebase.py      # PUT /merge_requests/:iid/rebase
│       ├── mocked_gitlab_merge.py       # PUT /merge_requests/:iid/merge
│       ├── mocked_gitlab_pipelines.py   # GET /pipelines/:id, GET /merge_requests/:iid/pipelines
│       ├── mocked_gitlab_comments.py    # POST/PUT /merge_requests/:iid/notes
│       ├── mocked_gitlab_notes.py       # GET /merge_requests/:iid/notes
│       ├── mocked_gitlab_conflicts.py   # GET /merge_requests/:iid/conflicts
│       ├── mocked_gitlab_jobs.py        # POST /jobs/:id/retry, GET /pipelines/:id/jobs
│       └── mocked_gitlab_rate_limit.py  # Rate limit response handling
```

### Rule
One file should contain mocks for **one URL pattern** only.

---

## Final Directory Structure

After all phases are complete:

```
scenarios/
├── config/
│   ├── secret/
│   │   ├── __init__.py
│   │   ├── create_secret.py
│   │   ├── get_secret_value.py
│   │   ├── secret_blocks_direct_access.py
│   │   └── ... (12 files total)
│   └── settings_validation/
│       ├── __init__.py
│       └── ... (14 files total)
├── core/
│   ├── queue_manager/
│   │   ├── __init__.py
│   │   └── ... (11 files total)
│   └── state_machine/
│       ├── __init__.py
│       └── ... (44 files total)
├── integration/
│   ├── api/
│   │   ├── analytics/
│   │   ├── auth/
│   │   ├── history/
│   │   ├── queue/
│   │   └── websocket/
│   ├── full_flow/
│   │   ├── concurrent/
│   │   ├── hotfix/
│   │   ├── multiple_mrs/
│   │   └── restart/
│   ├── scheduler/
│   └── webhook/
│       ├── flow/
│       └── pipeline/
├── models/
│   ├── events/
│   ├── mr/
│   ├── pipeline/
│   └── queue_item/
├── unit/
│   ├── circuit_breaker/
│   ├── gitlab_client/
│   │   ├── comments/
│   │   ├── errors/
│   │   ├── get_mr/
│   │   ├── list_mrs/
│   │   ├── merge/
│   │   ├── pipelines/
│   │   └── rebase/
│   ├── processor/
│   │   ├── conflict/
│   │   ├── pipeline_failure/
│   │   ├── shutdown/
│   │   └── timeout/
│   ├── queue/
│   │   ├── add_mr/          # DONE
│   │   ├── fifo_order/
│   │   ├── hotfix_priority/
│   │   └── remove_mr/
│   ├── rate_limit/
│   └── scheduler/
│       ├── shutdown/
│       └── sync/
├── webhooks/
│   ├── health/
│   ├── mr_webhook/
│   └── pipeline_webhook/
├── contexts/
│   ├── __init__.py          # Export all contexts
│   ├── api_helpers.py
│   ├── gitlab_client_factory.py
│   └── sqlite_client.py
├── mocks/
│   ├── __init__.py
│   └── gitlab/
│       ├── __init__.py
│       └── ... (mock files)
└── schemas/
    ├── __init__.py
    └── status_code.py
```

---

## Execution Order

| Step | Phase | Task | Estimated Time |
|------|-------|------|----------------|
| 1 | ~~Pilot~~ | ~~Update ruff.toml, convert processor_happy_path.py, split queue_add_mr.py~~ | ~~DONE~~ |
| 2 | 1 | Convert `unit/rate_limit.py` (19 scenarios) | 2 hours |
| 3 | 1 | Convert `unit/circuit_breaker.py` (16 scenarios) | 1.5 hours |
| 4 | 1 | Convert remaining 13 functional style files | 4 hours |
| 5 | 2 | Split `core/test_state_machine.py` (44 scenarios) | 2 hours |
| 6 | 2 | Split large files (>10 scenarios) | 4 hours |
| 7 | 2 | Split medium files (4-10 scenarios) | 4 hours |
| 8 | 2 | Split small files (≤3 scenarios) | 1 hour |
| 9 | 3 | Rename mocks (`mock_` → `mocked_`) | 30 min |
| 10 | 3 | Add `@vedro.context` and rename contexts | 1 hour |
| 11 | 3 | Update `contexts/__init__.py` exports | 30 min |
| 12 | ~~4~~ | ~~Update negative scenario subjects~~ | ~~DONE~~ |
| 13 | ~~5~~ | ~~Create status code schemas~~ | ~~DONE~~ |
| 14 | ~~6~~ | ~~Restructure mocks directory~~ | ~~DONE~~ |

**Total estimated time:** ~22 hours

---

## Validation Checklist

After each step, run:

```bash
# Lint check
cd backend && uv run ruff check scenarios/

# Type check
cd backend && make typecheck

# Run all tests
cd backend && uv run vedro run scenarios/

# Run tests with random order (find ordering bugs)
cd backend && uv run vedro run scenarios/ --order-random
```

---

## Notes

1. **Language:** Keep comments and docstrings in English (open-source project)
2. **Line length:** 120 characters (updated from 100)
3. **Test incrementally:** Run tests after each file conversion
4. **Commit often:** Create commits after completing each logical unit of work
