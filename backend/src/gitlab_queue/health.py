"""Application health state management.

Tracks the health status of all application components and provides
a unified view of system state for health endpoints and internal
decision making.

Example:
    >>> from gitlab_queue.health import ApplicationHealth, ComponentStatus
    >>> health = ApplicationHealth()
    >>> health.database = ComponentStatus.HEALTHY
    >>> health.mode
    <ApplicationMode.NORMAL: 'normal'>
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gitlab_queue.utils.circuit_breaker import CircuitBreaker


class ComponentStatus(Enum):
    """Health status for individual components."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ApplicationMode(Enum):
    """Overall application operating mode."""

    NORMAL = "normal"  # All components healthy
    DEGRADED = "degraded"  # Some components unavailable, core functions working
    UNHEALTHY = "unhealthy"  # Critical components down


@dataclass
class GitLabHealth:
    """GitLab API health status derived from circuit breaker.

    Attributes:
        status: Overall health status of GitLab connectivity.
        circuit_state: Current circuit breaker state ("closed", "open", "half_open").
        failure_count: Number of consecutive failures.
        retry_after_seconds: Seconds until circuit may attempt recovery (if open).
        last_checked: Timestamp of last health check.
    """

    status: ComponentStatus
    circuit_state: str
    failure_count: int
    retry_after_seconds: float | None = None
    last_checked: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_circuit_breaker(cls, cb: CircuitBreaker) -> GitLabHealth:
        """Create health status from circuit breaker state.

        Args:
            cb: Circuit breaker instance to derive health from.

        Returns:
            GitLabHealth with status derived from circuit state.
        """
        from gitlab_queue.utils.circuit_breaker import CircuitState

        if cb.state == CircuitState.CLOSED:
            status = ComponentStatus.HEALTHY
        elif cb.state == CircuitState.HALF_OPEN:
            status = ComponentStatus.DEGRADED
        else:  # OPEN
            status = ComponentStatus.UNHEALTHY

        return cls(
            status=status,
            circuit_state=cb.state.value,
            failure_count=cb.failure_count,
            retry_after_seconds=cb._time_until_half_open(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "status": self.status.value,
            "circuit_state": self.circuit_state,
            "failure_count": self.failure_count,
            "retry_after_seconds": self.retry_after_seconds,
            "last_checked": self.last_checked.isoformat(),
        }


@dataclass
class ApplicationHealth:
    """Overall application health state.

    Aggregates health from all components to determine operating mode
    and provide detailed status for health endpoints.

    Attributes:
        database: Database connection status.
        gitlab: GitLab API health (from circuit breaker).
        processor_running: Whether the MR processor is active.
        webhook_server_running: Whether the webhook server is accepting requests.
    """

    database: ComponentStatus = ComponentStatus.UNKNOWN
    gitlab: GitLabHealth | None = None
    processor_running: bool = False
    webhook_server_running: bool = False

    @property
    def mode(self) -> ApplicationMode:
        """Determine application operating mode from component status.

        Returns:
            UNHEALTHY if database is down.
            DEGRADED if GitLab is unavailable but database is healthy.
            NORMAL if all components are healthy.
        """
        # Database must be healthy for any operation
        if self.database != ComponentStatus.HEALTHY:
            return ApplicationMode.UNHEALTHY

        # GitLab unhealthy = degraded mode (can still queue events)
        if self.gitlab and self.gitlab.status == ComponentStatus.UNHEALTHY:
            return ApplicationMode.DEGRADED

        return ApplicationMode.NORMAL

    @property
    def is_ready(self) -> bool:
        """Check if application can accept requests.

        Ready when:
        - Database is healthy
        - Webhook server is running
        (GitLab can be down - events will be queued)

        Returns:
            True if ready to accept traffic.
        """
        return self.database == ComponentStatus.HEALTHY and self.webhook_server_running

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON response.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        result: dict[str, Any] = {
            "mode": self.mode.value,
            "is_ready": self.is_ready,
            "database": self.database.value,
            "processor_running": self.processor_running,
            "webhook_server_running": self.webhook_server_running,
        }

        if self.gitlab:
            result["gitlab"] = self.gitlab.to_dict()
        else:
            result["gitlab"] = {"status": ComponentStatus.UNKNOWN.value}

        return result


__all__: list[str] = [
    "ApplicationHealth",
    "ApplicationMode",
    "ComponentStatus",
    "GitLabHealth",
]
