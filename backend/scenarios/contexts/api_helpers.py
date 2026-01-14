"""API test helpers for Vedro scenarios.

Provides test utilities for creating test apps, JWT tokens, and seeding test data
for API endpoint testing.

Example:
    >>> from scenarios.contexts.api_helpers import create_test_app, create_test_jwt
    >>>
    >>> async with create_test_app() as (app, state):
    ...     client = TestClient(app)
    ...     token = create_test_jwt(state.settings)
    ...     response = client.get("/api/history", headers={"Authorization": f"Bearer {token}"})
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import jwt

from gitlab_queue.api.websocket import WebSocketManager
from gitlab_queue.config import Secret
from gitlab_queue.db.database import DatabaseStatus
from gitlab_queue.health import ApplicationHealth, ComponentStatus, GitLabHealth
from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.utils.circuit_breaker import CircuitBreaker, CircuitState
from gitlab_queue.webhooks.router import WebhookAppState, create_webhook_app
from scenarios.contexts.sqlite_client import test_database

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI

    from gitlab_queue.db.database import Database


# =============================================================================
# Mock Factories
# =============================================================================


def create_mock_settings(
    *,
    jwt_secret: str = "test-secret-key-for-jwt-tokens-12345",
    jwt_expiration_hours: int = 24,
    gitlab_url: str = "https://gitlab.example.com",
    gitlab_project_id: int = 123,
    queue_label: str = "merge_queue",
    hotfix_label: str = "hotfix",
    oauth_client_id: str | None = "test-client-id",
    oauth_client_secret: str | None = "test-client-secret",
    oauth_redirect_uri: str | None = "http://localhost:8080/auth/callback",
    webhook_secret: str | None = "test-webhook-secret",
) -> MagicMock:
    """Create mock settings for testing.

    Args:
        jwt_secret: JWT signing secret.
        jwt_expiration_hours: JWT token expiration in hours.
        gitlab_url: GitLab instance URL.
        gitlab_project_id: GitLab project ID.
        queue_label: Label for merge queue.
        hotfix_label: Label for hotfix priority.
        oauth_client_id: OAuth client ID.
        oauth_client_secret: OAuth client secret.
        oauth_redirect_uri: OAuth redirect URI.
        webhook_secret: Webhook validation secret.

    Returns:
        MagicMock: Mock settings object.
    """
    settings = MagicMock()
    settings.jwt_secret = Secret(jwt_secret)
    settings.jwt_expiration_hours = jwt_expiration_hours
    settings.gitlab_url = gitlab_url
    settings.gitlab_project_id = gitlab_project_id
    settings.gitlab_token = Secret("test-gitlab-token")
    settings.queue_label = queue_label
    settings.hotfix_label = hotfix_label
    settings.webhook_host = "0.0.0.0"
    settings.webhook_port = 8080
    settings.cors_origins = ["http://localhost:5173"]
    settings.dashboard_enabled = True
    settings.oauth_client_id = oauth_client_id
    settings.oauth_client_secret = oauth_client_secret
    settings.oauth_redirect_uri = oauth_redirect_uri
    settings.webhook_secret = Secret(webhook_secret) if webhook_secret else None
    return settings


def create_mock_database(*, connected: bool = True, wal_mode: bool = True) -> MagicMock:
    """Create mock database with configurable health status.

    Args:
        connected: Whether database is connected.
        wal_mode: Whether WAL mode is enabled.

    Returns:
        MagicMock: Mock database object.
    """
    db = MagicMock()
    db.health_check = AsyncMock(
        return_value=DatabaseStatus(
            connected=connected,
            wal_mode_enabled=wal_mode,
            foreign_keys_enabled=True,
            database_path="sqlite+aiosqlite:///:memory:",
            error=None if connected else "Connection failed",
        )
    )
    return db


def create_mock_circuit_breaker(state: CircuitState = CircuitState.CLOSED) -> MagicMock:
    """Create mock circuit breaker with configurable state.

    Args:
        state: Circuit breaker state.

    Returns:
        MagicMock: Mock circuit breaker object.
    """
    cb = MagicMock(spec=CircuitBreaker)
    cb.state = state
    cb.failure_count = 0 if state == CircuitState.CLOSED else 5
    cb.failure_threshold = 5
    cb.half_open_timeout = 30.0
    cb._time_until_half_open = MagicMock(return_value=None if state != CircuitState.OPEN else 25.0)
    return cb


def create_mock_gitlab_client(*, circuit_state: CircuitState = CircuitState.CLOSED) -> MagicMock:
    """Create mock GitLab client with circuit breaker.

    Args:
        circuit_state: Circuit breaker state.

    Returns:
        MagicMock: Mock GitLab client.
    """
    client = MagicMock()
    client.circuit_breaker = create_mock_circuit_breaker(circuit_state)
    client.rate_limit_state = MagicMock()
    client.rate_limit_state.limit = 2000
    client.rate_limit_state.remaining = 1900
    client.rate_limit_state.usage_ratio = 0.05
    client.rate_limit_state.seconds_until_reset = 3600
    return client


def create_mock_queue_manager() -> MagicMock:
    """Create mock queue manager.

    Returns:
        MagicMock: Mock queue manager.
    """
    qm = MagicMock()
    qm.get_active_queue = AsyncMock(return_value=[])
    qm.get_queue_stats = AsyncMock(
        return_value={"queued": 0, "rebasing": 0, "testing": 0, "merging": 0}
    )
    qm.get_recent_history = AsyncMock(return_value=[])
    qm.get_dashboard_stats = AsyncMock(
        return_value=MagicMock(
            total_in_queue=0,
            stats_window_days=7,
            merged_count=0,
            failed_count=0,
            success_rate=0.0,
            avg_wait_seconds=0,
            avg_processing_seconds=0,
        )
    )
    return qm


def create_mock_notifier() -> MagicMock:
    """Create mock MR notifier.

    Returns:
        MagicMock: Mock notifier.
    """
    return MagicMock()


def create_mock_retry_manager() -> MagicMock:
    """Create mock webhook retry manager.

    Returns:
        MagicMock: Mock retry manager.
    """
    manager = MagicMock()
    manager.get_dlq_entries = AsyncMock(return_value=[])
    manager.get_dlq_stats = AsyncMock(
        return_value=MagicMock(
            total_count=0,
            by_event_type={},
            oldest_entry=None,
        )
    )
    return manager


def create_mock_health(
    *,
    db_healthy: bool = True,
    gitlab_circuit_state: CircuitState = CircuitState.CLOSED,
) -> ApplicationHealth:
    """Create application health state.

    Args:
        db_healthy: Whether database is healthy.
        gitlab_circuit_state: GitLab circuit breaker state.

    Returns:
        ApplicationHealth: Health state object.
    """
    health = ApplicationHealth()
    health.database = ComponentStatus.HEALTHY if db_healthy else ComponentStatus.UNHEALTHY
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

    return health


# =============================================================================
# JWT Token Helpers
# =============================================================================


def create_test_jwt(
    settings: MagicMock,
    *,
    user_id: int = 12345,
    username: str = "testuser",
    name: str = "Test User",
    email: str = "test@example.com",
    avatar_url: str | None = "https://example.com/avatar.png",
    project_id: int | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a valid JWT token for testing.

    Args:
        settings: Mock settings with jwt_secret.
        user_id: GitLab user ID.
        username: GitLab username.
        name: User display name.
        email: User email.
        avatar_url: URL to user avatar.
        project_id: GitLab project ID (defaults to settings.gitlab_project_id).
        expires_delta: Token expiration time (defaults to settings.jwt_expiration_hours).

    Returns:
        str: Encoded JWT token.
    """
    now = datetime.now(UTC)

    if expires_delta is None:
        expires_delta = timedelta(hours=settings.jwt_expiration_hours)

    expire = now + expires_delta

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "name": name,
        "email": email,
        "avatar_url": avatar_url,
        "project_id": project_id or settings.gitlab_project_id,
        "exp": expire,
        "iat": now,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def create_expired_jwt(settings: MagicMock, **kwargs: Any) -> str:
    """Create an expired JWT token for testing.

    Args:
        settings: Mock settings with jwt_secret.
        **kwargs: Additional arguments passed to create_test_jwt.

    Returns:
        str: Expired JWT token.
    """
    return create_test_jwt(settings, expires_delta=timedelta(hours=-1), **kwargs)


def create_invalid_jwt() -> str:
    """Create an invalid JWT token for testing.

    Returns:
        str: Invalid JWT token string.
    """
    return "invalid.jwt.token"


# =============================================================================
# Test App Factory
# =============================================================================


def create_webhook_state(
    *,
    settings: MagicMock | None = None,
    database: MagicMock | None = None,
    db_healthy: bool = True,
    gitlab_circuit_state: CircuitState = CircuitState.CLOSED,
) -> WebhookAppState:
    """Create WebhookAppState with mocked dependencies.

    Args:
        settings: Optional custom settings mock.
        database: Optional custom database mock.
        db_healthy: Whether database should be healthy.
        gitlab_circuit_state: GitLab circuit breaker state.

    Returns:
        WebhookAppState: Configured app state.
    """
    return WebhookAppState(
        settings=settings or create_mock_settings(),
        database=database or create_mock_database(connected=db_healthy),
        gitlab_client=create_mock_gitlab_client(circuit_state=gitlab_circuit_state),
        queue_manager=create_mock_queue_manager(),
        notifier=create_mock_notifier(),
        retry_manager=create_mock_retry_manager(),
        health=create_mock_health(
            db_healthy=db_healthy,
            gitlab_circuit_state=gitlab_circuit_state,
        ),
        websocket_manager=WebSocketManager(),
    )


def create_test_app(
    *,
    settings: MagicMock | None = None,
    database: MagicMock | None = None,
    db_healthy: bool = True,
    gitlab_circuit_state: CircuitState = CircuitState.CLOSED,
) -> tuple[FastAPI, WebhookAppState]:
    """Create a test FastAPI app with mocked dependencies.

    Args:
        settings: Optional custom settings mock.
        database: Optional custom database mock.
        db_healthy: Whether database should be healthy.
        gitlab_circuit_state: GitLab circuit breaker state.

    Returns:
        Tuple of (FastAPI app, WebhookAppState).
    """
    state = create_webhook_state(
        settings=settings,
        database=database,
        db_healthy=db_healthy,
        gitlab_circuit_state=gitlab_circuit_state,
    )
    app = create_webhook_app(state)
    return app, state


@asynccontextmanager
async def create_test_app_with_db() -> AsyncIterator[tuple[FastAPI, WebhookAppState, Database]]:
    """Create a test FastAPI app with real in-memory database.

    This provides a fully functional app with real database for integration testing.

    Yields:
        Tuple of (FastAPI app, WebhookAppState, Database).
    """
    async with test_database() as db:
        settings = create_mock_settings()
        state = WebhookAppState(
            settings=settings,
            database=db,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=create_mock_queue_manager(),
            notifier=create_mock_notifier(),
            retry_manager=create_mock_retry_manager(),
            health=create_mock_health(),
            websocket_manager=WebSocketManager(),
        )
        app = create_webhook_app(state)
        yield app, state, db


# =============================================================================
# Test Data Helpers
# =============================================================================


def create_test_queue_item(
    *,
    mr_iid: int = 42,
    title: str = "Test MR",
    author_name: str = "Test Author",
    author_username: str = "testauthor",
    author_avatar: str | None = "https://example.com/avatar.png",
    state: str = "queued",
    is_hotfix: bool = False,
    labels: list[str] | None = None,
    target_branch: str = "main",
    queued_at: datetime | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    pipeline_id: int | None = None,
    pipeline_status: str | None = None,
    last_error: str | None = None,
    retry_count: int = 0,
) -> QueueItem:
    """Create a test QueueItem.

    Args:
        mr_iid: MR internal ID.
        title: MR title.
        author_name: Author display name.
        author_username: Author username.
        author_avatar: Author avatar URL.
        state: MR state (queued, rebasing, testing, merging, merged, failed).
        is_hotfix: Whether this is a hotfix.
        labels: MR labels.
        target_branch: Target branch.
        queued_at: Queue timestamp.
        started_at: Processing start timestamp.
        finished_at: Finish timestamp.
        pipeline_id: Pipeline ID.
        pipeline_status: Pipeline status.
        last_error: Last error message.
        retry_count: Retry count.

    Returns:
        QueueItem: Test queue item.
    """
    return QueueItem(
        mr_iid=mr_iid,
        title=title,
        author_name=author_name,
        author_username=author_username,
        author_avatar=author_avatar,
        state=state,
        is_hotfix=is_hotfix,
        labels=labels or ["merge_queue"],
        target_branch=target_branch,
        queued_at=queued_at or datetime.now(UTC),
        started_at=started_at,
        finished_at=finished_at,
        pipeline_id=pipeline_id,
        pipeline_status=pipeline_status,
        last_error=last_error,
        retry_count=retry_count,
    )


def create_test_history_items(count: int = 5) -> list[QueueItem]:
    """Create a list of test history items.

    Args:
        count: Number of items to create.

    Returns:
        List of QueueItem objects representing completed MRs.
    """
    items = []
    statuses = ["merged", "failed", "conflict", "timeout"]

    for i in range(count):
        status = statuses[i % len(statuses)]
        finished_at = datetime.now(UTC) - timedelta(hours=i)
        queued_at = finished_at - timedelta(minutes=30)
        started_at = queued_at + timedelta(minutes=5)

        items.append(
            create_test_queue_item(
                mr_iid=100 + i,
                title=f"Test MR #{100 + i}",
                state=status,
                queued_at=queued_at,
                started_at=started_at,
                finished_at=finished_at,
                last_error=f"Test error for {status}" if status != "merged" else None,
            )
        )

    return items


__all__ = [
    "create_expired_jwt",
    "create_invalid_jwt",
    "create_mock_circuit_breaker",
    "create_mock_database",
    "create_mock_gitlab_client",
    "create_mock_health",
    "create_mock_notifier",
    "create_mock_queue_manager",
    "create_mock_retry_manager",
    "create_mock_settings",
    "create_test_app",
    "create_test_app_with_db",
    "create_test_history_items",
    "create_test_jwt",
    "create_test_queue_item",
    "create_webhook_state",
]
