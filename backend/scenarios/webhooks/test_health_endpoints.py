"""Unit tests for health check endpoints."""

from unittest.mock import AsyncMock, MagicMock

import vedro
from fastapi.testclient import TestClient

from gitlab_queue.db.database import DatabaseStatus
from gitlab_queue.health import ApplicationHealth, ComponentStatus, GitLabHealth
from gitlab_queue.utils.circuit_breaker import CircuitBreaker, CircuitState
from gitlab_queue.webhooks.router import WebhookAppState, create_webhook_app


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
    )


class Scenario__health_returns_200_when_alive(vedro.Scenario):
    subject = "health endpoint returns 200 when process is alive"

    def given_webhook_app(self):
        state = create_webhook_state()
        self.app = create_webhook_app(state)
        self.client = TestClient(self.app)

    def when_health_endpoint_is_called(self):
        self.response = self.client.get("/health")

    def then_it_should_return_200_with_healthy_status(self):
        assert self.response.status_code == 200
        data = self.response.json()
        assert data["status"] == "healthy"
        assert "mode" in data
        assert "components" in data


class Scenario__ready_returns_200_when_db_healthy(vedro.Scenario):
    subject = "ready endpoint returns 200 when database is healthy"

    def given_webhook_app_with_healthy_db(self):
        state = create_webhook_state(db_connected=True)
        self.app = create_webhook_app(state)
        self.client = TestClient(self.app)

    def when_ready_endpoint_is_called(self):
        self.response = self.client.get("/ready")

    def then_it_should_return_200_with_healthy_database(self):
        assert self.response.status_code == 200
        data = self.response.json()
        assert data["status"] == "healthy"
        assert data["database"]["connected"] is True


class Scenario__ready_returns_503_when_db_unhealthy(vedro.Scenario):
    subject = "ready endpoint returns 503 when database is unhealthy"

    def given_webhook_app_with_unhealthy_db(self):
        state = create_webhook_state(db_connected=False)
        self.app = create_webhook_app(state)
        self.client = TestClient(self.app)

    def when_ready_endpoint_is_called(self):
        self.response = self.client.get("/ready")

    def then_it_should_return_503_with_error_reason(self):
        assert self.response.status_code == 503
        data = self.response.json()
        assert data["status"] == "unhealthy"
        assert data["reason"] == "database_unavailable"
        assert data["database"]["connected"] is False


class Scenario__ready_returns_200_when_gitlab_circuit_open(vedro.Scenario):
    subject = "ready endpoint returns 200 even when GitLab circuit is open"

    def given_webhook_app_with_open_circuit(self):
        state = create_webhook_state(
            db_connected=True,
            gitlab_circuit_state=CircuitState.OPEN,
        )
        self.app = create_webhook_app(state)
        self.client = TestClient(self.app)

    def when_ready_endpoint_is_called(self):
        self.response = self.client.get("/ready")

    def then_it_should_return_200_because_events_can_be_queued(self):
        # GitLab being down doesn't affect readiness - events get queued
        assert self.response.status_code == 200
        data = self.response.json()
        assert data["status"] == "healthy"
        assert data["database"]["connected"] is True
        # GitLab status should be reported but not affect readiness
        assert data["gitlab"]["status"] == "unhealthy"
        assert data["gitlab"]["circuit_state"] == "open"


class Scenario__health_detailed_returns_comprehensive_status(vedro.Scenario):
    subject = "health detailed endpoint returns comprehensive status"

    def given_webhook_app(self):
        state = create_webhook_state()
        self.app = create_webhook_app(state)
        self.client = TestClient(self.app)

    def when_health_detailed_endpoint_is_called(self):
        self.response = self.client.get("/health/detailed")

    def then_it_should_return_all_component_details(self):
        assert self.response.status_code == 200
        data = self.response.json()

        # Check all required fields are present
        assert "status" in data
        assert "mode" in data
        assert "database" in data
        assert "gitlab" in data
        assert "processor_running" in data
        assert "webhook_server_running" in data

        # Check database details
        assert "connected" in data["database"]
        assert "wal_mode_enabled" in data["database"]
        assert "foreign_keys_enabled" in data["database"]

        # Check GitLab details
        assert "status" in data["gitlab"]
        assert "circuit_breaker" in data["gitlab"]
        assert "rate_limit" in data["gitlab"]

        # Check circuit breaker details
        cb = data["gitlab"]["circuit_breaker"]
        assert "state" in cb
        assert "failure_count" in cb
        assert "failure_threshold" in cb

        # Check rate limit details
        rl = data["gitlab"]["rate_limit"]
        assert "limit" in rl
        assert "remaining" in rl
        assert "usage_ratio" in rl


class Scenario__health_includes_correlation_id_header(vedro.Scenario):
    subject = "health endpoints include X-Request-Id header"

    def given_webhook_app(self):
        state = create_webhook_state()
        self.app = create_webhook_app(state)
        self.client = TestClient(self.app)

    def when_health_endpoint_is_called(self):
        self.response = self.client.get("/health")

    def then_response_should_have_request_id_header(self):
        assert "x-request-id" in self.response.headers
        request_id = self.response.headers["x-request-id"]
        assert len(request_id) > 0
