"""Unit tests for Rate Limit Handling.

Tests the rate limit implementation including:
- RateLimitState dataclass calculations
- Adaptive throttling behavior
- Rate limit state updates from response headers
- Scheduler pause behavior at critical limit
"""

from __future__ import annotations

import time

import vedro
from vedro import scenario

from gitlab_queue.clients.gitlab import RateLimitState

# =============================================================================
# RateLimitState Usage Ratio Tests
# =============================================================================


@scenario()
async def usage_ratio_returns_none_when_limit_unknown():
    """Test that usage_ratio returns None when limit is not set."""
    with vedro.given:
        state = RateLimitState(limit=None, remaining=50)

    with vedro.when:
        ratio = state.usage_ratio

    with vedro.then:
        assert ratio is None


@scenario()
async def usage_ratio_returns_none_when_remaining_unknown():
    """Test that usage_ratio returns None when remaining is not set."""
    with vedro.given:
        state = RateLimitState(limit=100, remaining=None)

    with vedro.when:
        ratio = state.usage_ratio

    with vedro.then:
        assert ratio is None


@scenario()
async def usage_ratio_returns_none_when_limit_is_zero():
    """Test that usage_ratio returns None when limit is zero."""
    with vedro.given:
        state = RateLimitState(limit=0, remaining=0)

    with vedro.when:
        ratio = state.usage_ratio

    with vedro.then:
        assert ratio is None


@scenario()
async def usage_ratio_calculates_correctly_at_zero_usage():
    """Test usage_ratio is 0.0 when nothing has been used."""
    with vedro.given:
        state = RateLimitState(limit=100, remaining=100)

    with vedro.when:
        ratio = state.usage_ratio

    with vedro.then:
        assert ratio == 0.0


@scenario()
async def usage_ratio_calculates_correctly_at_50_percent():
    """Test usage_ratio is 0.5 when half has been used."""
    with vedro.given:
        state = RateLimitState(limit=100, remaining=50)

    with vedro.when:
        ratio = state.usage_ratio

    with vedro.then:
        assert ratio == 0.5


@scenario()
async def usage_ratio_calculates_correctly_at_80_percent():
    """Test usage_ratio is 0.8 when 80% has been used."""
    with vedro.given:
        state = RateLimitState(limit=100, remaining=20)

    with vedro.when:
        ratio = state.usage_ratio

    with vedro.then:
        assert ratio == 0.8


@scenario()
async def usage_ratio_calculates_correctly_at_full_usage():
    """Test usage_ratio is 1.0 when all quota is used."""
    with vedro.given:
        state = RateLimitState(limit=100, remaining=0)

    with vedro.when:
        ratio = state.usage_ratio

    with vedro.then:
        assert ratio == 1.0


# =============================================================================
# RateLimitState Threshold Tests
# =============================================================================


@scenario()
async def is_approaching_limit_returns_false_when_unknown():
    """Test is_approaching_limit returns False when ratio is unknown."""
    with vedro.given:
        state = RateLimitState(limit=None, remaining=None)

    with vedro.when:
        result = state.is_approaching_limit(threshold=0.8)

    with vedro.then:
        assert result is False


@scenario()
async def is_approaching_limit_returns_false_below_threshold():
    """Test is_approaching_limit returns False below threshold."""
    with vedro.given:
        state = RateLimitState(limit=100, remaining=30)  # 70% used

    with vedro.when:
        result = state.is_approaching_limit(threshold=0.8)

    with vedro.then:
        assert result is False


@scenario()
async def is_approaching_limit_returns_false_at_threshold():
    """Test is_approaching_limit returns False at exactly threshold."""
    with vedro.given:
        state = RateLimitState(limit=100, remaining=20)  # 80% used

    with vedro.when:
        result = state.is_approaching_limit(threshold=0.8)

    with vedro.then:
        # 0.8 > 0.8 is False
        assert result is False


@scenario()
async def is_approaching_limit_returns_true_above_threshold():
    """Test is_approaching_limit returns True above threshold."""
    with vedro.given:
        state = RateLimitState(limit=100, remaining=19)  # 81% used

    with vedro.when:
        result = state.is_approaching_limit(threshold=0.8)

    with vedro.then:
        assert result is True


@scenario()
async def is_critical_returns_false_when_unknown():
    """Test is_critical returns False when ratio is unknown."""
    with vedro.given:
        state = RateLimitState(limit=None, remaining=None)

    with vedro.when:
        result = state.is_critical(threshold=0.95)

    with vedro.then:
        assert result is False


@scenario()
async def is_critical_returns_false_below_threshold():
    """Test is_critical returns False below critical threshold."""
    with vedro.given:
        state = RateLimitState(limit=100, remaining=10)  # 90% used

    with vedro.when:
        result = state.is_critical(threshold=0.95)

    with vedro.then:
        assert result is False


@scenario()
async def is_critical_returns_true_at_critical():
    """Test is_critical returns True at critical level."""
    with vedro.given:
        state = RateLimitState(limit=100, remaining=4)  # 96% used

    with vedro.when:
        result = state.is_critical(threshold=0.95)

    with vedro.then:
        assert result is True


# =============================================================================
# RateLimitState Reset Time Tests
# =============================================================================


@scenario()
async def seconds_until_reset_returns_none_when_unknown():
    """Test seconds_until_reset returns None when reset_at is not set."""
    with vedro.given:
        state = RateLimitState(limit=100, remaining=50, reset_at=None)

    with vedro.when:
        result = state.seconds_until_reset

    with vedro.then:
        assert result is None


@scenario()
async def seconds_until_reset_returns_positive_for_future():
    """Test seconds_until_reset returns positive seconds for future reset."""
    with vedro.given:
        future_reset = int(time.time()) + 60  # 60 seconds from now
        state = RateLimitState(limit=100, remaining=50, reset_at=future_reset)

    with vedro.when:
        result = state.seconds_until_reset

    with vedro.then:
        assert result is not None
        assert 58 <= result <= 61  # Allow small timing variance


@scenario()
async def seconds_until_reset_returns_zero_for_past():
    """Test seconds_until_reset returns 0 for past reset time."""
    with vedro.given:
        past_reset = int(time.time()) - 60  # 60 seconds ago
        state = RateLimitState(limit=100, remaining=50, reset_at=past_reset)

    with vedro.when:
        result = state.seconds_until_reset

    with vedro.then:
        assert result is not None
        assert result == 0.0


# =============================================================================
# RateLimitState Factory Default Tests
# =============================================================================


@scenario()
async def rate_limit_state_initializes_with_defaults():
    """Test RateLimitState initializes with None values."""
    with vedro.given:
        pass

    with vedro.when:
        state = RateLimitState()

    with vedro.then:
        assert state.limit is None
        assert state.remaining is None
        assert state.reset_at is None
        assert state.last_updated > 0


@scenario()
async def rate_limit_state_initializes_with_values():
    """Test RateLimitState initializes with provided values."""
    with vedro.given:
        reset_time = int(time.time()) + 60

    with vedro.when:
        state = RateLimitState(
            limit=1000,
            remaining=500,
            reset_at=reset_time,
        )

    with vedro.then:
        assert state.limit == 1000
        assert state.remaining == 500
        assert state.reset_at == reset_time
        assert state.usage_ratio == 0.5
