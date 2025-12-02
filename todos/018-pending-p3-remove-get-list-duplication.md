---
status: pending
priority: p3
issue_id: "018"
tags: [code-review, simplification, gitlab-client]
dependencies: []
---

# Remove Duplicate get_list() Method

## Problem Statement

The client has separate `get()` and `get_list()` methods that differ only in return type annotation. This is unnecessary duplication - Python is dynamically typed and the caller knows what type to expect.

**Why it matters**: Reduces code duplication and maintenance burden.

## Findings

**Location**: `backend/src/gitlab_queue/clients/gitlab.py:344-388`

**get() method (lines 344-365)**:
```python
async def get(self, path: str, ...) -> dict[str, Any]:
    response = await self._request("GET", path, ...)
    result: dict[str, Any] = response.json()
    return result
```

**get_list() method (lines 367-388)**:
```python
async def get_list(self, path: str, ...) -> list[dict[str, Any]]:
    response = await self._request("GET", path, ...)
    result: list[dict[str, Any]] = response.json()
    return result
```

**Difference**: Only the return type annotation.

## Proposed Solutions

### Option A: Remove get_list() (Recommended)
Single `get()` method returning `Any`, let caller handle type.

```python
async def get(self, path: str, ...) -> Any:
    response = await self._request("GET", path, ...)
    return response.json()
```

**Pros**: 22 lines saved, no duplication
**Cons**: Loses type safety hint
**Effort**: Small (15 minutes)
**Risk**: Low

### Option B: Generic Return Type
Use TypeVar for return type.

```python
async def get[T](self, path: str, ..., return_type: type[T]) -> T:
```

**Pros**: Type-safe
**Cons**: Over-engineering
**Effort**: Medium (1 hour)
**Risk**: Low

### Option C: Keep Both (Do Nothing)
Accept duplication for type hint benefit.

**Pros**: Clear type hints
**Cons**: Duplication
**Effort**: None
**Risk**: None

## Recommended Action

<!-- Fill in after triage -->

## Technical Details

**Affected files**:
- `backend/src/gitlab_queue/clients/gitlab.py`

**Lines to remove**: 367-388 (if choosing Option A)

## Acceptance Criteria

- [ ] Decision made on method duplication
- [ ] If removing: update any callers
- [ ] If keeping: document reason

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created from code review | code-simplicity-reviewer flagged duplication |

## Resources

- PR: task-5 branch
