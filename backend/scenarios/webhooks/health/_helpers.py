"""Helper functions for health endpoint tests."""

from unittest.mock import AsyncMock, MagicMock

from gitlab_queue.api.websocket import WebSocketManager
from gitlab_queue.db.database import DatabaseStatus
from gitlab_queue.health import ApplicationHealth, ComponentStatus, GitLabHealth
from gitlab_queue.utils.circuit_breaker import CircuitBreaker, CircuitState
from gitlab_queue.webhooks.router import WebhookAppState


def create_mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.webhook_host = "0.0.0.0"
    settings.webhook_port = 8080
    settings.cors_origins = ["http://localhost:5173"]
    settings.dashboard_enabled = True
    return settings


def create_mock_database(connected: bool = True, wal_mode: bool = True):
    """Create mock database with configurable health status."""
    db = MagicMock()
    db.health_check = AsyncMock(
        return_value=DatabaseStatus(
            connected=connected,
            wal_mode_enabled=wal_mode,
            foreign_keys_enabled=True,
            database_path="sqlite+aiosqlite:///data/queue.db",
            error=None if connected else "Connection failed",
        )
    )
    return db


def create_mock_circuit_breaker(state: CircuitState = CircuitState.CLOSED):
    """Create mock circuit breaker with configurable state."""
    cb = MagicMock(spec=CircuitBreaker)
    cb.state = state
    cb.failure_count = 0 if state == CircuitState.CLOSED else 5
    cb.failure_threshold = 5
    cb.half_open_timeout = 30.0
    cb._time_until_half_open = MagicMock(return_value=None if state != CircuitState.OPEN else 25.0)
    return cb


def create_mock_gitlab_client(circuit_state: CircuitState = CircuitState.CLOSED):
    """Create mock GitLab client with circuit breaker."""
    client = MagicMock()
    client.circuit_breaker = create_mock_circuit_breaker(circuit_state)
    client.rate_limit_state = MagicMock()
    client.rate_limit_state.limit = 2000
    client.rate_limit_state.remaining = 1900
    client.rate_limit_state.usage_ratio = 0.05
    client.rate_limit_state.seconds_until_reset = 3600
    return client


def create_mock_queue_manager():
    """Create mock queue manager."""
    qm = MagicMock()
    return qm


def create_mock_notifier():
    """Create mock MR notifier."""
    return MagicMock()


def create_mock_retry_manager():
    """Create mock webhook retry manager."""
    return MagicMock()


def create_webhook_state(
    db_connected: bool = True,
    gitlab_circuit_state: CircuitState = CircuitState.CLOSED,
) -> WebhookAppState:
    """Create WebhookAppState with mocked dependencies."""
    health = ApplicationHealth()
    health.database = ComponentStatus.HEALTHY if db_connected else ComponentStatus.UNHEALTHY
    health.processor_running = True
    health.webhook_server_running = True

    if gitlab_circuit_state == CircuitState.CLOSED:
        health.gitlab = GitLabHealth(
            status=ComponentStatus.HEALTHY,
            circuit_state="closed",
            failure_count=0,
        )
    elif gitlab_circuit_state == CircuitState.OPEN:
        health.gitlab = GitLabHealth(
            status=ComponentStatus.UNHEALTHY,
            circuit_state="open",
            failure_count=5,
            retry_after_seconds=25.0,
        )
    else:
        health.gitlab = GitLabHealth(
            status=ComponentStatus.DEGRADED,
            circuit_state="half_open",
            failure_count=5,
        )

    return WebhookAppState(
        settings=create_mock_settings(),
        database=create_mock_database(connected=db_connected),
        gitlab_client=create_mock_gitlab_client(circuit_state=gitlab_circuit_state),
        queue_manager=create_mock_queue_manager(),
        notifier=create_mock_notifier(),
        retry_manager=create_mock_retry_manager(),
        health=health,
        websocket_manager=WebSocketManager(),
    )
