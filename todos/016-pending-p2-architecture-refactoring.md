---
status: pending
priority: p2
issue_id: "016"
tags: [code-review, architecture, gitlab-client]
dependencies: ["011", "012", "013", "014", "015"]
---

# Architecture Refactoring for Tasks 6-8

## Problem Statement

The current `GitLabClient` class has multiple responsibilities (SRP violation) and will become a 1000+ line God Object when Tasks 6-8 add MR, Pipeline, and Comment operations. The architecture needs refactoring before these tasks.

**Why it matters**: Without refactoring, the codebase will become difficult to maintain, test, and extend. Each new task will add complexity to an already complex class.

## Findings

**Location**: `backend/src/gitlab_queue/clients/gitlab.py:80-457`

**Current Responsibilities (8+)**:
1. HTTP client lifecycle management (lines 106-141)
2. Authentication (lines 104-114)
3. Rate limit handling (lines 276-286)
4. Error response parsing (lines 183-193, 194-274)
5. Header parsing (lines 155-181)
6. Path construction (lines 143-153)
7. Retry logic orchestration (lines 288-342)
8. Generic HTTP operations (lines 344-456)

**Tasks 6-8 Requirements** (from roadmap):
- Task 6: MR Operations - get_mr, list_mrs_with_label, rebase_mr, check_rebase_status
- Task 7: Pipeline Operations - get_mr_pipelines, get_pipeline_status, retry_pipeline_job
- Task 8: Merge/Comment - merge_mr, add_comment, update_comment, add_or_update_pinned_comment

**Risk**: Adding 12+ methods directly to GitLabClient will bloat it to 1000+ lines.

## Proposed Solutions

### Option A: Layered Architecture (Recommended)
Split into Transport + Resource Clients pattern.

```
Layer 2: Resource Clients (Tasks 6-8)
- MergeRequestClient (Task 6)
- PipelineClient (Task 7)
- CommentClient (Task 8)

Layer 1: Transport (Current GitLabClient, renamed)
- GitLabTransport - HTTP operations only
```

**Pros**: Clean separation, easy to add new resource types
**Cons**: Larger refactor, changes import paths
**Effort**: Large (1-2 days)
**Risk**: Medium (but worth it)

### Option B: Incremental Refactoring
Keep GitLabClient for now, create resource clients gradually during Tasks 6-8.

**Pros**: Delivers value incrementally
**Cons**: Technical debt accumulates initially
**Effort**: Spread across Tasks 6-8
**Risk**: Low

### Option C: Full Refactor Now
Refactor completely before Task 6.

**Pros**: Clean architecture from start
**Cons**: Delays Task 6
**Effort**: Very Large (1 week)
**Risk**: High (scope creep)

## Recommended Action

<!-- Fill in after triage -->

## Technical Details

**Affected files**:
- `backend/src/gitlab_queue/clients/gitlab.py` (split into multiple files)

**Proposed structure**:
```
src/gitlab_queue/clients/
├── __init__.py              # Export GitLabClient facade
├── transport.py             # GitLabTransport (HTTP operations)
├── errors.py                # Exception hierarchy
├── resources/
│   ├── __init__.py
│   ├── merge_requests.py    # Task 6
│   ├── pipelines.py         # Task 7
│   └── comments.py          # Task 8
└── gitlab.py                # GitLabClient facade
```

## Acceptance Criteria

- [ ] GitLabClient under 300 lines
- [ ] Clear separation between transport and resource logic
- [ ] Easy to add new resource types
- [ ] Existing functionality preserved
- [ ] Unit tests updated

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created from code review | architecture-strategist flagged SRP violations |

## Resources

- PR: task-5 branch
- Tasks 6-8 in roadmap/initial_plan.md
