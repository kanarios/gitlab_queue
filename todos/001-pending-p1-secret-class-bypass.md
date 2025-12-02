---
status: completed
priority: p1
issue_id: "001"
tags: [code-review, security, python]
dependencies: []
---

# Secret Class Direct Attribute Access Bypass

## Problem Statement

The `Secret` class in `config.py` can be bypassed using standard Python attribute access, allowing direct extraction of sensitive values. This defeats the purpose of the secret wrapper.

**Why it matters**: Any code that receives a `Secret` object can extract the plaintext value, potentially exposing tokens, passwords, and other sensitive data in logs or error messages.

## Findings

**File**: `/Users/artemkuznecov/repos/gitlab_queue/backend/src/gitlab_queue/config.py`
**Lines**: 59-98 (Secret class)
**Severity**: CRITICAL
**CVSS Score**: 7.5 (High)

### Evidence

```python
secret = Secret("glpat-sensitive-token-12345")
value = secret._secret_value  # Direct access works!
value = getattr(secret, "_secret_value")  # Also works!
```

The `__slots__` usage prevents `__dict__` access but does NOT prevent direct attribute access. The underscore prefix `_secret_value` is a naming convention only.

### Impact
- Any code that receives a Secret object can extract the plaintext value
- Debugging tools, error handlers, or logging that use getattr() will expose secrets
- Reflection/introspection code bypasses protection

## Proposed Solutions

### Option A: Add `__getattribute__` Override
**Description**: Block direct attribute access to `_secret_value`

```python
def __getattribute__(self, name: str) -> Any:
    if name == "_secret_value":
        raise AttributeError("Direct access to secret value is not allowed. Use get_secret_value()")
    return object.__getattribute__(self, name)
```

**Pros**:
- Simple fix
- Maintains existing API

**Cons**:
- Determined attackers could still use `object.__getattribute__`

**Effort**: Small (30 mins)
**Risk**: Low

### Option B: Use External Library (pydantic.SecretStr)
**Description**: Replace custom Secret class with battle-tested library

**Pros**:
- Battle-tested implementation
- Better integration with Pydantic ecosystem

**Cons**:
- Breaking change for existing code
- Additional dependency

**Effort**: Medium (2-4 hours)
**Risk**: Medium

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected Files**:
- `backend/src/gitlab_queue/config.py` (lines 59-98)

**Affected Components**:
- Configuration loading
- Secret handling throughout application

## Acceptance Criteria

- [ ] Direct attribute access to `_secret_value` raises AttributeError
- [ ] `getattr(secret, "_secret_value")` raises AttributeError
- [ ] `get_secret_value()` method still works correctly
- [ ] Existing tests pass
- [ ] New tests added for bypass prevention

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created finding from security review | Identified bypass vector |

## Resources

- PR: Current branch `feat/config-module`
- Security Review: security-sentinel agent analysis
