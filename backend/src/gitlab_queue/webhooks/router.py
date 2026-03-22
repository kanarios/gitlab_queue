"""FastAPI application for GitLab webhooks.

Provides webhook endpoints for receiving GitLab events (MR updates, pipeline
status changes) and health check endpoints for container orchestration.

Example:
    >>> from gitlab_queue.webhooks import WebhookAppState, create_webhook_app
    >>> state = WebhookAppState(settings=settings, database=db, ...)
    >>> app = create_webhook_app(state)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from gitlab_queue.api.routes import analytics_router, config_router, history_router
from gitlab_queue.api.websocket import WebSocketManager, ws_router
from gitlab_queue.auth.middleware import AuthenticationMiddleware
from gitlab_queue.auth.routes import auth_router
from gitlab_queue.clients.gitlab import GitLabCircuitOpenError
from gitlab_queue.core.queue import QueueItemNotFoundError
from gitlab_queue.health import ApplicationHealth, ComponentStatus, GitLabHealth
from gitlab_queue.metrics import (
    METRICS_CONTENT_TYPE,
    get_metrics_output,
    update_gitlab_metrics,
    update_queue_metrics,
)
from gitlab_queue.models.events import MergeRequestEvent, PipelineEvent, validate_webhook_token
from gitlab_queue.models.retorts import parse_webhook_event
from gitlab_queue.utils.logging import LogContext, generate_request_id, get_logger
from gitlab_queue.webhooks.handlers import MRWebhookHandler, PipelineWebhookHandler, WebhookHandler
from gitlab_queue.webhooks.retry_manager import DLQItemNotFoundError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    import httpx

    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.core.notifier import MRNotifier
    from gitlab_queue.core.queue import QueueManager
    from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier
    from gitlab_queue.db import UnitOfWork
    from gitlab_queue.db.database import Database
    from gitlab_queue.models.queue_item import DashboardStats, QueueItem
    from gitlab_queue.models.retry import DLQItem, DLQStats
    from gitlab_queue.webhooks.retry_manager import WebhookRetryManager

log = get_logger(__name__)


# =============================================================================
# Application State
# =============================================================================


@dataclass(slots=True)
class WebhookAppState:
    """Shared state for webhook handlers.

    Contains references to all application components needed by webhook
    handlers to process incoming events.

    Attributes:
        settings: Application configuration.
        database: Database connection manager.
        gitlab_client: GitLab API client for making API calls.
        queue_manager: Queue manager for MR queue operations.
        notifier: MR notifier for state machine notifications.
        position_notifier: Queue position notifier for position change notifications.
        retry_manager: Webhook retry queue manager.
        health: Application health state for status endpoints.
        websocket_manager: WebSocket manager for real-time dashboard updates.
    """

    settings: Settings
    database: Database
    gitlab_client: GitLabClient
    queue_manager: QueueManager
    notifier: MRNotifier
    position_notifier: QueuePositionNotifier | None
    retry_manager: WebhookRetryManager
    health: ApplicationHealth
    websocket_manager: WebSocketManager
    event_router: Callable[[WebhookAppState, MergeRequestEvent | PipelineEvent], Awaitable[None]] | None = field(
        default=None
    )
    oauth_transport: httpx.AsyncBaseTransport | None = field(default=None)
    uow_factory: Callable[[Database], UnitOfWork] | None = field(default=None)


# =============================================================================
# Lifespan Management
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage FastAPI application lifecycle.

    Handles startup and shutdown events for the webhook server.
    Logs server start/stop events with relevant configuration.

    Args:
        app: The FastAPI application instance.

    Yields:
        None - Control returns to FastAPI for request handling.
    """
    state: WebhookAppState = app.state.webhook_state

    log.info(
        "Webhook server starting",
        host=state.settings.webhook_host,
        port=state.settings.webhook_port,
    )

    yield

    log.info("Webhook server shutting down")


# =============================================================================
# Correlation ID Middleware
# =============================================================================


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware that adds correlation IDs to all requests.

    Generates a unique request ID for each incoming request and sets it
    in the logging context. Also adds the X-Request-Id header to responses.

    The correlation ID format is: {timestamp_ms}-{random_hex}
    Example: "1733500000000-a1b2c3d4"
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request with correlation ID context."""
        request_id = generate_request_id()

        # Add to request state for access in handlers
        request.state.request_id = request_id

        # Log with correlation ID context
        with LogContext(request_id=request_id):
            log.debug(
                "Request started",
                method=request.method,
                path=request.url.path,
            )

            response = await call_next(request)

            # Add correlation ID to response headers
            response.headers["X-Request-Id"] = request_id

            log.debug(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
            )

        return response


# =============================================================================
# Health Check Router
# =============================================================================

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    """Liveness probe endpoint.

    Returns 200 OK if the process is running. Used by container
    orchestration systems (Docker, Kubernetes) to determine if
    the container should be restarted.

    Includes component status for debugging but always returns 200.
    For readiness, use /ready endpoint.

    Returns:
        dict: Status with component details.
    """
    state: WebhookAppState = request.app.state.webhook_state

    # Update GitLab health from circuit breaker
    if state.gitlab_client and state.gitlab_client.circuit_breaker:
        state.health.gitlab = GitLabHealth.from_circuit_breaker(state.gitlab_client.circuit_breaker)

    return {
        "status": "healthy",
        "mode": state.health.mode.value,
        "components": state.health.to_dict(),
    }


@health_router.get("/ready", response_model=None)
async def ready(request: Request) -> JSONResponse | dict[str, Any]:
    """Readiness probe endpoint.

    Checks if the application is ready to receive traffic:
    - Database must be connected (required)
    - GitLab status is reported but doesn't affect readiness
      (webhooks can be queued even if GitLab is down)

    Args:
        request: FastAPI request object for accessing app state.

    Returns:
        200 if ready to accept traffic (database healthy).
        503 if database is unhealthy.
    """
    state: WebhookAppState = request.app.state.webhook_state

    # Check database health
    db_status = await state.database.health_check()

    # Update health state
    state.health.database = ComponentStatus.HEALTHY if db_status.connected else ComponentStatus.UNHEALTHY

    # Update GitLab health from circuit breaker
    gitlab_info: dict[str, Any] | None = None
    if state.gitlab_client and state.gitlab_client.circuit_breaker:
        state.health.gitlab = GitLabHealth.from_circuit_breaker(state.gitlab_client.circuit_breaker)
        gitlab_info = {
            "status": state.health.gitlab.status.value,
            "circuit_state": state.health.gitlab.circuit_state,
            "retry_after_seconds": state.health.gitlab.retry_after_seconds,
        }

    if not db_status.connected:
        log.warning(
            "Readiness check failed: database unhealthy",
            error=db_status.error,
        )
        return JSONResponse(
            content={
                "status": "unhealthy",
                "reason": "database_unavailable",
                "database": {
                    "connected": False,
                    "error": db_status.error,
                },
                "gitlab": gitlab_info,
            },
            status_code=503,
        )

    # Ready even if GitLab is down (events will be queued)
    return {
        "status": "healthy",
        "mode": state.health.mode.value,
        "database": {
            "connected": True,
            "wal_mode": db_status.wal_mode_enabled,
        },
        "gitlab": gitlab_info,
    }


@health_router.get("/health/detailed")
async def health_detailed(request: Request) -> dict[str, Any]:
    """Detailed health endpoint for debugging and monitoring.

    Returns comprehensive health information including all
    component states, circuit breaker details, and rate limit status.

    This endpoint always returns 200 (for observability) but
    includes all details needed to diagnose issues.

    Returns:
        dict: Comprehensive health information for all components.
    """
    state: WebhookAppState = request.app.state.webhook_state

    # Database health
    db_status = await state.database.health_check()

    # GitLab health from circuit breaker
    cb = state.gitlab_client.circuit_breaker
    gitlab_health = GitLabHealth.from_circuit_breaker(cb)

    # Rate limit state
    rate_limit = state.gitlab_client.rate_limit_state

    return {
        "status": "ok",
        "mode": state.health.mode.value,
        "config": {
            "gitlab_project_id": state.settings.gitlab_project_id,
            "target_branch": state.settings.target_branch,
            "queue_label": state.settings.queue_label,
            "hotfix_label": state.settings.hotfix_label,
        },
        "database": {
            "connected": db_status.connected,
            "wal_mode_enabled": db_status.wal_mode_enabled,
            "foreign_keys_enabled": db_status.foreign_keys_enabled,
            "error": db_status.error,
        },
        "gitlab": {
            "status": gitlab_health.status.value,
            "circuit_breaker": {
                "state": cb.state.value,
                "failure_count": cb.failure_count,
                "failure_threshold": cb.failure_threshold,
                "half_open_timeout_seconds": cb.half_open_timeout,
                "retry_after_seconds": gitlab_health.retry_after_seconds,
            },
            "rate_limit": {
                "limit": rate_limit.limit,
                "remaining": rate_limit.remaining,
                "usage_ratio": rate_limit.usage_ratio,
                "seconds_until_reset": rate_limit.seconds_until_reset,
            },
        },
        "processor_running": state.health.processor_running,
        "webhook_server_running": state.health.webhook_server_running,
    }


@health_router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    """Prometheus metrics endpoint.

    Exposes application metrics in Prometheus text format for scraping.
    Updates queue and GitLab metrics on each request to ensure fresh data.

    Args:
        request: FastAPI request object for accessing app state.

    Returns:
        Response with Prometheus text format metrics.
    """
    state: WebhookAppState = request.app.state.webhook_state

    # Update current metrics from application state
    await update_queue_metrics(state.queue_manager, state.settings.gitlab_project_id)
    update_gitlab_metrics(state.gitlab_client)

    return Response(
        content=get_metrics_output(),
        media_type=METRICS_CONTENT_TYPE,
    )


# =============================================================================
# Webhook Router
# =============================================================================

webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _route_webhook_event(
    state: WebhookAppState,
    event: MergeRequestEvent | PipelineEvent,
) -> None:
    """Route webhook event to appropriate handler.

    Args:
        state: Webhook application state.
        event: Parsed webhook event.
    """
    if isinstance(event, MergeRequestEvent):
        handler = MRWebhookHandler(
            settings=state.settings,
            gitlab_client=state.gitlab_client,
            queue_manager=state.queue_manager,
            notifier=state.notifier,
            position_notifier=state.position_notifier,
            websocket_manager=state.websocket_manager,
        )
        await handler.handle(event)
    elif isinstance(event, PipelineEvent):
        pipeline_handler = PipelineWebhookHandler(
            settings=state.settings,
            gitlab_client=state.gitlab_client,
            queue_manager=state.queue_manager,
            notifier=state.notifier,
            position_notifier=state.position_notifier,
            websocket_manager=state.websocket_manager,
        )
        await pipeline_handler.handle(event)


def _validate_webhook_request(
    state: WebhookAppState,
    x_gitlab_token: str,
) -> None:
    """Validate webhook token.

    Args:
        state: Webhook application state.
        x_gitlab_token: Token from request header.

    Raises:
        HTTPException: If validation fails.
    """
    if state.settings.webhook_secret is None:
        log.error("Webhook secret not configured")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    if not validate_webhook_token(
        x_gitlab_token,
        state.settings.webhook_secret.get_secret_value(),
    ):
        log.warning("Invalid webhook token received")
        raise HTTPException(status_code=401, detail="Invalid webhook token")


@webhook_router.post("/gitlab", response_model=None)
async def handle_gitlab_webhook(
    request: Request,
    x_gitlab_token: str = Header(alias="X-Gitlab-Token"),
) -> dict[str, Any] | JSONResponse:
    """Handle incoming GitLab webhook events."""
    state: WebhookAppState = request.app.state.webhook_state

    _validate_webhook_request(state, x_gitlab_token)

    payload = await request.json()

    try:
        event = parse_webhook_event(payload)
    except (ValueError, KeyError) as e:
        log.warning(
            "Failed to parse webhook event",
            error=str(e),
            object_kind=payload.get("object_kind"),
        )
        try:
            retry_id = await state.retry_manager.add_to_retry_queue(
                event_type=payload.get("object_kind", "unknown"),
                payload=payload,
                error=str(e),
            )
            return {"status": "queued_for_retry", "retry_id": str(retry_id)}
        except Exception:
            return {"status": "error", "reason": "parse_failed"}

    if event is None:
        log.debug("Unknown event type ignored", object_kind=payload.get("object_kind"))
        return {
            "status": "ignored",
            "reason": "unknown_event_type",
            "details": {"object_kind": payload.get("object_kind")},
        }

    if event.project_id != state.settings.gitlab_project_id:
        log.debug(
            "Event for different project ignored",
            event_project_id=event.project_id,
            configured_project_id=state.settings.gitlab_project_id,
        )
        return {
            "status": "ignored",
            "reason": "project_id_mismatch",
            "details": {
                "event_project_id": event.project_id,
                "configured_project_id": state.settings.gitlab_project_id,
            },
        }

    # Only route MR and Pipeline events
    if not isinstance(event, MergeRequestEvent | PipelineEvent):
        log.debug("Unsupported event type ignored", event_type=type(event).__name__)
        return {
            "status": "ignored",
            "reason": "unsupported_event_type",
            "details": {"event_type": type(event).__name__},
        }

    try:
        route_fn = state.event_router or _route_webhook_event
        await route_fn(state, event)
    except GitLabCircuitOpenError as e:
        log.warning(
            "Webhook handling failed: GitLab circuit open",
            event_type=type(event).__name__,
            retry_after=e.retry_after,
        )
        return JSONResponse(
            content={
                "status": "service_unavailable",
                "error": "GitLab API temporarily unavailable",
                "retry_after": int(e.retry_after or 30),
            },
            status_code=503,
            headers={"Retry-After": str(int(e.retry_after or 30))},
        )
    except QueueItemNotFoundError as e:
        log.info(
            "MR not found in queue, ignoring webhook event",
            mr_iid=e.mr_iid,
            event_type=type(event).__name__,
        )
        return {"status": "ignored", "reason": "mr_not_in_queue"}
    except Exception as e:
        log.exception(
            "Error handling webhook event",
            event_type=type(event).__name__,
            project_id=event.project_id,
        )

        try:
            retry_id = await state.retry_manager.add_to_retry_queue(
                event_type=event.object_kind,
                payload=payload,
                error=str(e),
            )
            log.info(
                "Failed event added to retry queue",
                retry_id=retry_id,
                event_type=event.object_kind,
            )
            return {"status": "queued_for_retry", "retry_id": str(retry_id)}
        except Exception as retry_error:
            log.exception(
                "Failed to add event to retry queue",
                error=str(retry_error),
            )
            return {"status": "error"}

    return {"status": "ok"}


# =============================================================================
# DLQ API Router
# =============================================================================

dlq_router = APIRouter(prefix="/api/dlq", tags=["dlq"])


@dlq_router.get("")
async def list_dlq_entries(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    event_type: str | None = None,
) -> dict[str, Any]:
    """List DLQ entries with optional filtering.

    Args:
        request: FastAPI request object.
        limit: Maximum number of items to return (default: 50).
        offset: Number of items to skip for pagination.
        event_type: Optional filter by event type ('merge_request' or 'pipeline').

    Returns:
        Dict with items list and stats.
    """
    state: WebhookAppState = request.app.state.webhook_state

    items = await state.retry_manager.get_dlq_entries(
        limit=limit,
        offset=offset,
        event_type=event_type,
    )
    stats = await state.retry_manager.get_dlq_stats()

    return {
        "items": [_dlq_item_to_dict(item) for item in items],
        "stats": _dlq_stats_to_dict(stats),
        "pagination": {
            "limit": limit,
            "offset": offset,
        },
    }


@dlq_router.get("/stats")
async def get_dlq_stats(request: Request) -> dict[str, Any]:
    """Get DLQ statistics.

    Args:
        request: FastAPI request object.

    Returns:
        DLQ statistics dict.
    """
    state: WebhookAppState = request.app.state.webhook_state
    stats = await state.retry_manager.get_dlq_stats()
    return _dlq_stats_to_dict(stats)


@dlq_router.get("/{entry_id}")
async def get_dlq_entry(request: Request, entry_id: int) -> dict[str, Any]:
    """Get a single DLQ entry by ID.

    Args:
        request: FastAPI request object.
        entry_id: ID of the DLQ entry.

    Returns:
        DLQ entry dict.

    Raises:
        HTTPException: 404 if entry not found.
    """
    state: WebhookAppState = request.app.state.webhook_state

    try:
        item = await state.retry_manager.get_dlq_entry(entry_id)
        return _dlq_item_to_dict(item)
    except DLQItemNotFoundError:
        raise HTTPException(status_code=404, detail=f"DLQ entry {entry_id} not found")


@dlq_router.delete("/{entry_id}")
async def delete_dlq_entry(request: Request, entry_id: int) -> dict[str, str]:
    """Delete a DLQ entry.

    Args:
        request: FastAPI request object.
        entry_id: ID of the DLQ entry to delete.

    Returns:
        Status dict.

    Raises:
        HTTPException: 404 if entry not found.
    """
    state: WebhookAppState = request.app.state.webhook_state

    deleted = await state.retry_manager.delete_dlq_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"DLQ entry {entry_id} not found")

    return {"status": "deleted", "entry_id": str(entry_id)}


@dlq_router.post("/{entry_id}/retry")
async def retry_dlq_entry(request: Request, entry_id: int) -> dict[str, Any]:
    """Move a DLQ entry back to retry queue for another attempt.

    Args:
        request: FastAPI request object.
        entry_id: ID of the DLQ entry to retry.

    Returns:
        Status dict with new retry queue ID.

    Raises:
        HTTPException: 404 if entry not found.
    """
    state: WebhookAppState = request.app.state.webhook_state

    try:
        retry_id = await state.retry_manager.retry_dlq_entry(entry_id)
        log.info(
            "DLQ entry moved to retry queue",
            dlq_entry_id=entry_id,
            retry_id=retry_id,
        )
        return {
            "status": "requeued",
            "dlq_entry_id": entry_id,
            "retry_id": retry_id,
        }
    except DLQItemNotFoundError:
        raise HTTPException(status_code=404, detail=f"DLQ entry {entry_id} not found")


def _dlq_item_to_dict(item: DLQItem) -> dict[str, Any]:
    """Convert DLQItem to dict for JSON response."""
    return {
        "id": item.id,
        "event_type": item.event_type,
        "payload": item.payload,
        "attempt_count": item.attempt_count,
        "last_error": item.last_error,
        "original_created_at": item.original_created_at.isoformat(),
        "moved_to_dlq_at": item.moved_to_dlq_at.isoformat(),
    }


def _dlq_stats_to_dict(stats: DLQStats) -> dict[str, Any]:
    """Convert DLQStats to dict for JSON response."""
    return {
        "total_count": stats.total_count,
        "by_event_type": stats.by_event_type,
        "oldest_entry": stats.oldest_entry.isoformat() if stats.oldest_entry else None,
    }


# =============================================================================
# Queue Dashboard API Router
# =============================================================================

queue_router = APIRouter(prefix="/api/queue", tags=["queue"])


@queue_router.get("")
async def get_queue_status(request: Request) -> dict[str, Any]:
    """Get complete queue status for dashboard.

    Returns the current queue state, recent history, and aggregate
    statistics for display on the status dashboard.

    Args:
        request: FastAPI request object.

    Returns:
        Dict with queue, history, and stats sections.
    """
    state: WebhookAppState = request.app.state.webhook_state
    queue_manager = state.queue_manager

    project_id = state.settings.gitlab_project_id
    active_queue = await queue_manager.get_active_queue(project_id)
    recent_history = await queue_manager.get_recent_history(limit=10)
    dashboard_stats = await queue_manager.get_dashboard_stats(days=7)
    current_stats = await queue_manager.get_queue_stats(project_id)

    return {
        "queue": [_queue_item_to_dict(item, position=idx + 1) for idx, item in enumerate(active_queue)],
        "history": [_queue_item_to_dict(item) for item in recent_history],
        "stats": _dashboard_stats_to_dict(dashboard_stats, current_stats),
    }


@queue_router.get("/active")
async def get_active_queue(request: Request) -> dict[str, Any]:
    """Get only the active queue items.

    Lighter-weight endpoint for just the current queue state.

    Args:
        request: FastAPI request object.

    Returns:
        Dict with queue items and count.
    """
    state: WebhookAppState = request.app.state.webhook_state
    queue_manager = state.queue_manager

    project_id = state.settings.gitlab_project_id
    active_queue = await queue_manager.get_active_queue(project_id)

    return {
        "items": [_queue_item_to_dict(item, position=idx + 1) for idx, item in enumerate(active_queue)],
        "count": len(active_queue),
    }


@queue_router.get("/stats")
async def get_queue_statistics(request: Request) -> dict[str, Any]:
    """Get queue statistics only.

    Args:
        request: FastAPI request object.

    Returns:
        Dict with current and historical statistics.
    """
    state: WebhookAppState = request.app.state.webhook_state
    queue_manager = state.queue_manager

    project_id = state.settings.gitlab_project_id
    dashboard_stats = await queue_manager.get_dashboard_stats(days=7)
    current_stats = await queue_manager.get_queue_stats(project_id)

    return _dashboard_stats_to_dict(dashboard_stats, current_stats)


@queue_router.get("/{mr_iid}")
async def get_queue_item(request: Request, mr_iid: int) -> dict[str, Any]:
    """Get a specific MR's queue status.

    Args:
        request: FastAPI request object.
        mr_iid: The MR's internal ID.

    Returns:
        Dict with MR queue item details and position.

    Raises:
        HTTPException: 404 if MR not found in queue.
    """
    state: WebhookAppState = request.app.state.webhook_state
    queue_manager = state.queue_manager

    project_id = state.settings.gitlab_project_id
    item = await queue_manager.get_queue_item(project_id, mr_iid)
    if item is None:
        raise HTTPException(status_code=404, detail=f"MR !{mr_iid} not found in queue")

    position = await queue_manager.get_queue_position(project_id, mr_iid)

    return _queue_item_to_dict(item, position=position)


def _queue_item_to_dict(item: QueueItem, position: int | None = None) -> dict[str, Any]:
    """Convert QueueItem to dict for JSON response.

    Args:
        item: The queue item to serialize.
        position: Optional position in queue (1-indexed).

    Returns:
        Dict suitable for JSON serialization.
    """
    result: dict[str, Any] = {
        "mr_iid": item.mr_iid,
        "title": item.title,
        "author": {
            "name": item.author_name,
            "username": item.author_username,
            "avatar_url": item.author_avatar,
        },
        "target_branch": item.target_branch,
        "state": item.state,
        "is_hotfix": item.is_hotfix,
        "labels": item.labels,
        "queued_at": item.queued_at.isoformat(),
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
    }

    # Add position for active queue items
    if position is not None:
        result["position"] = position

    # Add pipeline info if available
    if item.pipeline_id is not None:
        result["pipeline"] = {
            "id": item.pipeline_id,
            "status": item.pipeline_status,
        }

    # Add error info for failed items
    if item.last_error:
        result["last_error"] = item.last_error
        result["retry_count"] = item.get_max_job_retry_count()

    return result


def _dashboard_stats_to_dict(
    stats: DashboardStats,
    current_stats: dict[str, int],
) -> dict[str, Any]:
    """Convert dashboard stats to dict for JSON response.

    Args:
        stats: Aggregate statistics from DashboardStats.
        current_stats: Current queue counts by status.

    Returns:
        Dict with all statistics.
    """
    return {
        "current": {
            "total": stats.total_in_queue,
            "by_status": current_stats,
        },
        "historical": {
            "window_days": stats.stats_window_days,
            "merged_count": stats.merged_count,
            "failed_count": stats.failed_count,
            "success_rate_percent": stats.success_rate,
        },
        "timing": {
            "avg_wait_seconds": stats.avg_wait_seconds,
            "avg_processing_seconds": stats.avg_processing_seconds,
        },
    }


# =============================================================================
# Application Factory
# =============================================================================


def create_webhook_app(state: WebhookAppState) -> FastAPI:
    """Create and configure the FastAPI webhook application.

    Sets up the FastAPI app with:
    - Lifespan events for startup/shutdown
    - CORS middleware for cross-origin requests
    - Health check endpoints (/health, /ready)
    - Shared application state

    Args:
        state: Shared state containing all application dependencies.

    Returns:
        Configured FastAPI application ready to serve requests.

    Example:
        >>> state = WebhookAppState(
        ...     settings=settings,
        ...     database=database,
        ...     gitlab_client=gitlab_client,
        ...     queue_manager=queue_manager,
        ... )
        >>> app = create_webhook_app(state)
        >>> # Run with uvicorn
        >>> config = uvicorn.Config(app, host="0.0.0.0", port=8080)
        >>> server = uvicorn.Server(config)
        >>> await server.serve()
    """
    app = FastAPI(
        title="GitLab Merge Queue Webhooks",
        description="Webhook receiver for GitLab Merge Queue Bot",
        version="1.0.0",
        lifespan=lifespan,
        # Disable automatic docs in production if needed
        docs_url="/docs" if state.settings.dashboard_enabled else None,
        redoc_url=None,
    )

    # Store shared state for access in route handlers
    app.state.webhook_state = state

    # Configure CORS for dashboard frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=state.settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    # Add authentication middleware for protected routes
    # Skips public paths: /health, /ready, /auth/*, /webhooks/*
    app.add_middleware(AuthenticationMiddleware, settings=state.settings)

    # Add correlation ID middleware for request tracking
    app.add_middleware(CorrelationIdMiddleware)

    # Register routers
    app.include_router(health_router)
    app.include_router(webhook_router)
    app.include_router(dlq_router)
    app.include_router(queue_router)
    app.include_router(history_router)
    app.include_router(analytics_router)
    app.include_router(config_router)
    app.include_router(auth_router)
    app.include_router(ws_router)

    log.debug(
        "Webhook app configured",
        cors_origins=state.settings.cors_origins,
        docs_enabled=state.settings.dashboard_enabled,
    )

    return app


__all__: list[str] = [
    "WebhookAppState",
    "WebhookHandler",
    "analytics_router",
    "auth_router",
    "config_router",
    "create_webhook_app",
    "dlq_router",
    "health_router",
    "history_router",
    "queue_router",
    "webhook_router",
    "ws_router",
]
