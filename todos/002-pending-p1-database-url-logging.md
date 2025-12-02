---
status: completed
priority: p1
issue_id: "002"
tags: [code-review, security, logging]
dependencies: []
---

# Database URL Credentials Not Masked in Logs

## Problem Statement

Database connection strings with embedded credentials are NOT masked by the logging sensitive data patterns. This means database passwords can appear in plaintext in logs.

**Why it matters**: Database credentials logged in plaintext during errors or debugging could be exposed in log aggregation systems, leading to unauthorized database access.

## Findings

**File**: `/Users/artemkuznecov/repos/gitlab_queue/backend/src/gitlab_queue/utils/logging.py`
**Lines**: 44-59 (sensitive patterns)
**Severity**: CRITICAL
**CVSS Score**: 7.5 (High)

### Evidence

```python
# Input
"postgresql://user:myPassword123@localhost/db"

# Current Output (LEAKED!)
"postgresql://user:myPassword123@localhost/db"

# Expected Output
"postgresql://user:***@localhost/db"
```

No regex pattern in `_SENSITIVE_PATTERNS` matches database URLs with embedded credentials. The masking in `config.py:_mask_database_url()` only applies to Settings repr, not to general logging.

### Impact
- Database credentials logged in plaintext during errors
- Credentials exposed in structured logs (JSON format)
- Log aggregation systems store plaintext database passwords

## Proposed Solutions

### Option A: Add Database URL Pattern
**Description**: Add regex pattern to mask credentials in database URLs

```python
# Add to _SENSITIVE_PATTERNS at line 59:
(re.compile(r"://([^:/@]+):([^@]+)@", re.IGNORECASE), r"://\1:***@"),
```

**Pros**:
- Simple fix
- Matches standard database URL format

**Cons**:
- May need multiple patterns for different URL formats

**Effort**: Small (15 mins)
**Risk**: Low

### Option B: Use urlparse for Complete Masking
**Description**: Parse URLs and mask password component

**Pros**:
- More robust URL handling
- Handles edge cases

**Cons**:
- More complex implementation
- Performance overhead per log message

**Effort**: Medium (1-2 hours)
**Risk**: Low

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected Files**:
- `backend/src/gitlab_queue/utils/logging.py` (lines 44-59)

**Database URL Formats to Consider**:
- `postgresql://user:password@host/db`
- `mysql://user:password@host:3306/db`
- `sqlite+aiosqlite:///path` (no credentials)
- `mongodb://user:password@host:27017/db`

## Acceptance Criteria

- [ ] Database URLs with passwords are masked in logs
- [ ] Pattern handles common database URL formats
- [ ] Existing tests pass
- [ ] New test added for database URL masking

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created finding from security review | Database URLs not covered by current patterns |

## Resources

- PR: Current branch `feat/config-module`
- Security Review: security-sentinel agent analysis
