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
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from gitlab_queue.models.events import MergeRequestEvent, PipelineEvent, validate_webhook_token
from gitlab_queue.models.retorts import parse_webhook_event
from gitlab_queue.utils.logging import get_logger
from gitlab_queue.webhooks.handlers import MRWebhookHandler, PipelineWebhookHandler
from gitlab_queue.webhooks.retry_manager import DLQItemNotFoundError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.core.notifier import MRNotifier
    from gitlab_queue.core.queue import QueueManager
    from gitlab_queue.db.database import Database
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
        retry_manager: Webhook retry queue manager.
    """

    settings: Settings
    database: Database
    gitlab_client: GitLabClient
    queue_manager: QueueManager
    notifier: MRNotifier
    retry_manager: WebhookRetryManager


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
# Health Check Router
# =============================================================================

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe endpoint.

    Returns 200 OK if the process is running. Used by container
    orchestration systems (Docker, Kubernetes) to determine if
    the container should be restarted.

    Returns:
        dict: Status indicating the server is healthy.
    """
    return {"status": "healthy"}


@health_router.get("/ready")
async def ready(request: Request) -> JSONResponse | dict[str, Any]:
    """Readiness probe endpoint.

    Checks if the application is ready to receive traffic by verifying
    database connectivity. Used by load balancers and orchestration
    systems to determine if traffic should be routed to this instance.

    Args:
        request: FastAPI request object for accessing app state.

    Returns:
        200 with status if healthy, 503 with error details if unhealthy.
    """
    state: WebhookAppState = request.app.state.webhook_state

    # Check database health
    db_status = await state.database.health_check()

    if not db_status.connected:
        log.warning(
            "Readiness check failed: database unhealthy",
            error=db_status.error,
        )
        return JSONResponse(
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": db_status.error,
            },
            status_code=503,
        )

    return {
        "status": "healthy",
        "database": "connected",
        "wal_mode": db_status.wal_mode_enabled,
    }


# =============================================================================
# Webhook Router
# =============================================================================

webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@webhook_router.post("/gitlab")
async def handle_gitlab_webhook(
    request: Request,
    x_gitlab_token: str = Header(alias="X-Gitlab-Token"),
) -> dict[str, str]:
    """Handle incoming GitLab webhook events.

    Validates the webhook token, parses the event payload, and routes
    to the appropriate handler based on event type.

    Args:
        request: FastAPI request object.
        x_gitlab_token: GitLab webhook secret token from header.

    Returns:
        Status dict indicating event processing result.

    Raises:
        HTTPException: 401 if webhook token is invalid.
    """
    state: WebhookAppState = request.app.state.webhook_state

    # Validate webhook token
    if state.settings.webhook_secret is None:
        log.error("Webhook secret not configured")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    if not validate_webhook_token(
        x_gitlab_token,
        state.settings.webhook_secret.get_secret_value(),
    ):
        log.warning("Invalid webhook token received")
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    # Parse event payload
    payload = await request.json()
    event = parse_webhook_event(payload)

    if event is None:
        log.debug("Unknown event type ignored", object_kind=payload.get("object_kind"))
        return {"status": "ignored"}

    # Validate project ID
    if event.project_id != state.settings.gitlab_project_id:
        log.debug(
            "Event for different project ignored",
            event_project_id=event.project_id,
            configured_project_id=state.settings.gitlab_project_id,
        )
        return {"status": "ignored"}

    # Route to appropriate handler
    try:
        if isinstance(event, MergeRequestEvent):
            handler = MRWebhookHandler(
                settings=state.settings,
                gitlab_client=state.gitlab_client,
                queue_manager=state.queue_manager,
            )
            await handler.handle(event)
        elif isinstance(event, PipelineEvent):
            pipeline_handler = PipelineWebhookHandler(
                settings=state.settings,
                gitlab_client=state.gitlab_client,
                queue_manager=state.queue_manager,
                notifier=state.notifier,
            )
            await pipeline_handler.handle(event)
    except Exception as e:
        # Log error and add to retry queue
        log.exception(
            "Error handling webhook event",
            event_type=type(event).__name__,
            project_id=event.project_id,
        )

        # Add to retry queue for later processing
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

    # Register routers
    app.include_router(health_router)
    app.include_router(webhook_router)
    app.include_router(dlq_router)

    log.debug(
        "Webhook app configured",
        cors_origins=state.settings.cors_origins,
        docs_enabled=state.settings.dashboard_enabled,
    )

    return app


__all__: list[str] = [
    "WebhookAppState",
    "create_webhook_app",
    "dlq_router",
    "health_router",
    "webhook_router",
]
