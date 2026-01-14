"""Circuit breaker implementation for external service protection.

Implements the circuit breaker pattern to prevent cascading failures
when external services (like GitLab API) are unavailable.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service is unavailable, requests fail immediately
- HALF_OPEN: Testing if service recovered, allowing probe requests

Example:
    >>> from gitlab_queue.utils.circuit_breaker import CircuitBreaker
    >>> cb = CircuitBreaker(failure_threshold=5, half_open_timeout=30.0)
    >>> try:
    ...     await cb.call(some_async_function, arg1, arg2)
    ... except CircuitOpenError:
    ...     # Handle circuit open - fail fast
    ...     pass
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar

from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from gitlab_queue.config import Settings

log = get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open and blocking requests.

    Attributes:
        retry_after: Time in seconds until circuit may attempt half-open.
    """

    def __init__(
        self,
        message: str = "Circuit breaker is open",
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class CircuitBreaker:
    """Async-compatible circuit breaker for external service protection.

    Thread-safe via asyncio.Lock for state transitions.

    Attributes:
        failure_threshold: Consecutive failures before circuit opens.
        half_open_timeout: Seconds before trying half-open probe.
        success_threshold: Successes in half-open to close circuit.
        name: Identifier for logging.
    """

    failure_threshold: int = 5
    half_open_timeout: float = 30.0
    success_threshold: int = 1
    name: str = "default"

    # Internal state (not init params)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: datetime | None = field(default=None, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Current consecutive failure count."""
        return self._failure_count

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try half-open."""
        if self._last_failure_time is None:
            return False
        elapsed = datetime.now(UTC) - self._last_failure_time
        return elapsed >= timedelta(seconds=self.half_open_timeout)

    def _time_until_half_open(self) -> float | None:
        """Return seconds until circuit can attempt half-open."""
        if self._state != CircuitState.OPEN:
            return None
        if self._last_failure_time is None:
            return None

        elapsed = (datetime.now(UTC) - self._last_failure_time).total_seconds()
        remaining = self.half_open_timeout - elapsed
        return max(0.0, remaining)

    async def record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                log.info(
                    "Circuit breaker half-open success",
                    name=self.name,
                    success_count=self._success_count,
                    success_threshold=self.success_threshold,
                )
                if self._success_count >= self.success_threshold:
                    self._transition_to_closed()
            else:
                # Reset failure count on success in closed state
                self._failure_count = 0

    async def record_failure(self, exception: BaseException) -> None:
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(UTC)

            log.warning(
                "Circuit breaker recorded failure",
                name=self.name,
                failure_count=self._failure_count,
                failure_threshold=self.failure_threshold,
                state=self._state.value,
                exception_type=type(exception).__name__,
            )

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open immediately opens circuit
                self._transition_to_open()
            elif self._failure_count >= self.failure_threshold:
                self._transition_to_open()

    def _transition_to_open(self) -> None:
        """Transition circuit to open state."""
        previous_state = self._state
        self._state = CircuitState.OPEN
        self._success_count = 0

        log.error(
            "Circuit breaker opened",
            name=self.name,
            previous_state=previous_state.value,
            failure_count=self._failure_count,
            half_open_timeout_seconds=self.half_open_timeout,
        )

    def _transition_to_half_open(self) -> None:
        """Transition circuit to half-open state."""
        previous_state = self._state
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0

        log.info(
            "Circuit breaker half-open",
            name=self.name,
            previous_state=previous_state.value,
        )

    def _transition_to_closed(self) -> None:
        """Transition circuit to closed state."""
        previous_state = self._state
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None

        log.info(
            "Circuit breaker closed",
            name=self.name,
            previous_state=previous_state.value,
        )

    async def before_call(self) -> None:
        """Check if call should proceed. Raises CircuitOpenError if blocked."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return

            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                    return

                retry_after = self._time_until_half_open()
                raise CircuitOpenError(
                    f"Circuit breaker '{self.name}' is open. "
                    f"Will attempt recovery in {retry_after:.1f}s",
                    retry_after=retry_after,
                )

            # HALF_OPEN: allow the probe request
            return

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute function with circuit breaker protection.

        Args:
            func: Async function to call.
            *args: Positional arguments for func.
            **kwargs: Keyword arguments for func.

        Returns:
            Result of func.

        Raises:
            CircuitOpenError: If circuit is open.
            Exception: Any exception from func (after recording failure).
        """
        await self.before_call()

        try:
            result = await func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as e:
            await self.record_failure(e)
            raise

    def reset(self) -> None:
        """Reset circuit breaker to initial closed state.

        Useful for testing or manual intervention.
        """
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None

        log.info("Circuit breaker reset", name=self.name)


def create_circuit_breaker(settings: Settings, name: str = "gitlab") -> CircuitBreaker:
    """Factory function to create configured circuit breaker.

    Args:
        settings: Application settings.
        name: Identifier for this circuit breaker.

    Returns:
        Configured CircuitBreaker instance.
    """
    return CircuitBreaker(
        failure_threshold=settings.circuit_breaker_failure_threshold,
        half_open_timeout=settings.circuit_breaker_half_open_timeout_seconds,
        success_threshold=settings.circuit_breaker_success_threshold,
        name=name,
    )


__all__: list[str] = [
    "CircuitBreaker",
    "CircuitOpenError",
    "CircuitState",
    "create_circuit_breaker",
]
