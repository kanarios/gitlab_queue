"""Unit tests for CircuitBreaker.

Tests the circuit breaker pattern implementation including:
- State transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Failure counting and threshold behavior
- Success handling and circuit recovery
- Thread safety via asyncio.Lock
"""

from __future__ import annotations

import asyncio

import vedro
from vedro import scenario

from gitlab_queue.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)

# =============================================================================
# Initial State Tests
# =============================================================================


@scenario()
async def circuit_breaker_starts_closed():
    """Test that circuit breaker starts in CLOSED state."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            half_open_timeout=30.0,
            success_threshold=1,
            name="test",
        )

    with vedro.when:
        state = circuit_breaker.state
        failure_count = circuit_breaker.failure_count

    with vedro.then:
        assert state == CircuitState.CLOSED
        assert failure_count == 0


# =============================================================================
# Failure Handling Tests
# =============================================================================


@scenario()
async def circuit_opens_after_failure_threshold():
    """Test that circuit opens after reaching failure threshold."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            half_open_timeout=30.0,
            name="test",
        )

    with vedro.when:
        # Record failures up to threshold
        for i in range(3):
            await circuit_breaker.record_failure(Exception(f"failure {i}"))

        state = circuit_breaker.state

    with vedro.then:
        assert state == CircuitState.OPEN


@scenario()
async def circuit_stays_closed_below_threshold():
    """Test that circuit stays closed when failures are below threshold."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            half_open_timeout=30.0,
            name="test",
        )

    with vedro.when:
        # Record fewer failures than threshold
        await circuit_breaker.record_failure(Exception("failure 1"))
        await circuit_breaker.record_failure(Exception("failure 2"))

        state = circuit_breaker.state
        failure_count = circuit_breaker.failure_count

    with vedro.then:
        assert state == CircuitState.CLOSED
        assert failure_count == 2


@scenario()
async def success_resets_failure_count():
    """Test that a success resets the failure count in CLOSED state."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            half_open_timeout=30.0,
            name="test",
        )

    with vedro.when:
        # Accumulate some failures
        await circuit_breaker.record_failure(Exception("failure 1"))
        await circuit_breaker.record_failure(Exception("failure 2"))

        # Record a success
        await circuit_breaker.record_success()

        failure_count = circuit_breaker.failure_count

    with vedro.then:
        assert failure_count == 0


# =============================================================================
# Circuit Open Behavior Tests
# =============================================================================


@scenario()
async def open_circuit_blocks_calls():
    """Test that open circuit raises CircuitOpenError."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            half_open_timeout=60.0,  # Long timeout to prevent half-open
            name="test",
        )
        # Open the circuit
        await circuit_breaker.record_failure(Exception("failure 1"))
        await circuit_breaker.record_failure(Exception("failure 2"))

        assert circuit_breaker.state == CircuitState.OPEN

    with vedro.when:
        error = None
        try:
            await circuit_breaker.before_call()
        except CircuitOpenError as e:
            error = e

    with vedro.then:
        assert error is not None
        assert error.retry_after is not None
        assert error.retry_after > 0


@scenario()
async def open_circuit_includes_retry_after():
    """Test that CircuitOpenError includes retry_after information."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            half_open_timeout=30.0,
            name="test",
        )
        await circuit_breaker.record_failure(Exception("failure 1"))
        await circuit_breaker.record_failure(Exception("failure 2"))

    with vedro.when:
        error = None
        try:
            await circuit_breaker.before_call()
        except CircuitOpenError as e:
            error = e

    with vedro.then:
        assert error is not None
        # retry_after should be close to half_open_timeout (30 seconds)
        assert error.retry_after is not None
        assert 29 <= error.retry_after <= 30


# =============================================================================
# Half-Open State Tests
# =============================================================================


@scenario()
async def circuit_transitions_to_half_open_after_timeout():
    """Test that circuit transitions to HALF_OPEN after timeout."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            half_open_timeout=0.1,  # 100ms timeout for fast test
            name="test",
        )
        await circuit_breaker.record_failure(Exception("failure 1"))
        await circuit_breaker.record_failure(Exception("failure 2"))

        assert circuit_breaker.state == CircuitState.OPEN

    with vedro.when:
        # Wait for timeout
        await asyncio.sleep(0.15)

        # Next call should transition to half-open
        await circuit_breaker.before_call()

        state = circuit_breaker.state

    with vedro.then:
        assert state == CircuitState.HALF_OPEN


@scenario()
async def half_open_closes_on_success():
    """Test that circuit closes after success in HALF_OPEN state."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            half_open_timeout=0.1,
            success_threshold=1,
            name="test",
        )
        # Open circuit
        await circuit_breaker.record_failure(Exception("failure 1"))
        await circuit_breaker.record_failure(Exception("failure 2"))

        # Wait for half-open
        await asyncio.sleep(0.15)
        await circuit_breaker.before_call()

        assert circuit_breaker.state == CircuitState.HALF_OPEN

    with vedro.when:
        # Record success in half-open
        await circuit_breaker.record_success()

        state = circuit_breaker.state

    with vedro.then:
        assert state == CircuitState.CLOSED


@scenario()
async def half_open_opens_on_failure():
    """Test that circuit opens immediately on failure in HALF_OPEN state."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(
            failure_threshold=5,  # Higher threshold
            half_open_timeout=0.1,
            name="test",
        )
        # Open circuit
        for _ in range(5):
            await circuit_breaker.record_failure(Exception("failure"))

        # Wait for half-open
        await asyncio.sleep(0.15)
        await circuit_breaker.before_call()

        assert circuit_breaker.state == CircuitState.HALF_OPEN

    with vedro.when:
        # Record failure in half-open
        await circuit_breaker.record_failure(Exception("failure in half-open"))

        state = circuit_breaker.state

    with vedro.then:
        assert state == CircuitState.OPEN


@scenario()
async def half_open_requires_success_threshold():
    """Test that circuit requires success_threshold successes to close."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            half_open_timeout=0.1,
            success_threshold=3,  # Need 3 successes
            name="test",
        )
        # Open circuit
        await circuit_breaker.record_failure(Exception("failure 1"))
        await circuit_breaker.record_failure(Exception("failure 2"))

        # Wait for half-open
        await asyncio.sleep(0.15)
        await circuit_breaker.before_call()

        assert circuit_breaker.state == CircuitState.HALF_OPEN

    with vedro.when:
        # Record 2 successes (not enough)
        await circuit_breaker.record_success()
        await circuit_breaker.record_success()

        state_after_2 = circuit_breaker.state

        # Record 3rd success
        await circuit_breaker.record_success()

        state_after_3 = circuit_breaker.state

    with vedro.then:
        assert state_after_2 == CircuitState.HALF_OPEN
        assert state_after_3 == CircuitState.CLOSED


# =============================================================================
# Call Wrapper Tests
# =============================================================================


@scenario()
async def call_method_executes_function():
    """Test that call() executes the wrapped function."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(name="test")
        call_count = 0

        async def test_func():
            nonlocal call_count
            call_count += 1
            return "success"

    with vedro.when:
        result = await circuit_breaker.call(test_func)

    with vedro.then:
        assert result == "success"
        assert call_count == 1


@scenario()
async def call_method_records_success():
    """Test that call() records success on successful execution."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(failure_threshold=5, name="test")

        # Add a failure first
        await circuit_breaker.record_failure(Exception("initial failure"))
        assert circuit_breaker.failure_count == 1

        async def success_func():
            return "ok"

    with vedro.when:
        await circuit_breaker.call(success_func)
        failure_count = circuit_breaker.failure_count

    with vedro.then:
        assert failure_count == 0  # Reset by success


@scenario()
async def call_method_records_failure_and_raises():
    """Test that call() records failure and re-raises exception."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(failure_threshold=5, name="test")

        async def failing_func():
            raise ValueError("test error")

    with vedro.when:
        error = None
        try:
            await circuit_breaker.call(failing_func)
        except ValueError as e:
            error = e

        failure_count = circuit_breaker.failure_count

    with vedro.then:
        assert error is not None
        assert str(error) == "test error"
        assert failure_count == 1


@scenario()
async def call_method_blocks_when_open():
    """Test that call() raises CircuitOpenError when circuit is open."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            half_open_timeout=60.0,
            name="test",
        )
        # Open circuit
        await circuit_breaker.record_failure(Exception("failure 1"))
        await circuit_breaker.record_failure(Exception("failure 2"))

        call_count = 0

        async def test_func():
            nonlocal call_count
            call_count += 1
            return "should not be called"

    with vedro.when:
        error = None
        try:
            await circuit_breaker.call(test_func)
        except CircuitOpenError as e:
            error = e

    with vedro.then:
        assert error is not None
        assert call_count == 0  # Function was never called


# =============================================================================
# Reset Tests
# =============================================================================


@scenario()
async def reset_returns_to_closed_state():
    """Test that reset() returns circuit to initial CLOSED state."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            half_open_timeout=60.0,
            name="test",
        )
        # Open circuit
        await circuit_breaker.record_failure(Exception("failure 1"))
        await circuit_breaker.record_failure(Exception("failure 2"))

        assert circuit_breaker.state == CircuitState.OPEN

    with vedro.when:
        circuit_breaker.reset()

        state = circuit_breaker.state
        failure_count = circuit_breaker.failure_count

    with vedro.then:
        assert state == CircuitState.CLOSED
        assert failure_count == 0


# =============================================================================
# Concurrency Tests
# =============================================================================


@scenario()
async def concurrent_failures_are_counted_correctly():
    """Test that concurrent failure recordings are thread-safe."""
    with vedro.given:
        circuit_breaker = CircuitBreaker(
            failure_threshold=100,  # High threshold
            name="test",
        )

        async def record_failure():
            await circuit_breaker.record_failure(Exception("concurrent failure"))

    with vedro.when:
        # Fire 50 concurrent failures
        await asyncio.gather(*[record_failure() for _ in range(50)])

        failure_count = circuit_breaker.failure_count

    with vedro.then:
        assert failure_count == 50
