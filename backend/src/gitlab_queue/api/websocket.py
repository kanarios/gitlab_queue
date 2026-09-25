"""WebSocket manager for real-time dashboard updates.

Provides WebSocket connections for pushing queue state changes to connected
dashboard clients in real-time.

Example:
    >>> from gitlab_queue.api.websocket import WebSocketManager, ws_router
    >>> manager = WebSocketManager()
    >>> app.include_router(ws_router)
    >>> # Broadcast to all clients
    >>> await manager.broadcast_mr_status_changed(42, "queued", "rebasing")
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from gitlab_queue.auth.jwt_handler import (
    InvalidTokenError,
    TokenExpiredError,
    decode_token,
    get_authorized_project_ids,
)
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.config import Settings
    from gitlab_queue.models.queue_item import QueueItem

log = get_logger(__name__)


# =============================================================================
# WebSocket Manager
# =============================================================================


class WebSocketManager:
    """Manages WebSocket connections and broadcasts queue updates.

    This class handles:
    - Connection management (connect/disconnect)
    - JWT token validation for new connections
    - Broadcasting events to all connected clients
    - Graceful handling of disconnections during broadcasts

    Attributes:
        _connections: Set of active WebSocket connections.

    Example:
        >>> manager = WebSocketManager()
        >>> # In websocket endpoint
        >>> if await manager.connect(websocket, token, settings):
        ...     try:
        ...         while True:
        ...             await websocket.receive_text()
        ...     except WebSocketDisconnect:
        ...         await manager.disconnect(websocket)
    """

    def __init__(self) -> None:
        """Initialize the WebSocket manager with empty connections."""
        self._connections: set[WebSocket] = set()
        self._project_connections: dict[int, set[WebSocket]] = {}

    @property
    def connection_count(self) -> int:
        """Return the number of active connections."""
        return len(self._connections)

    async def connect(
        self,
        websocket: WebSocket,
        token: str | None,
        settings: Settings,
        project_id: int | None = None,
    ) -> bool:
        """Validate token and accept WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept.
            token: JWT token from query parameter.
            settings: Application settings for token validation.

        Returns:
            True if connection was accepted, False if rejected.
        """
        if not token:
            log.warning("WebSocket connection rejected: missing token")
            await websocket.close(code=1008, reason="Missing token")
            return False

        try:
            payload = decode_token(token, settings)
            if project_id is not None and project_id not in get_authorized_project_ids(payload):
                log.warning(
                    "WebSocket connection rejected: project access denied",
                    project_id=project_id,
                    user_id=payload.get("sub"),
                )
                await websocket.close(code=1008, reason="Project access denied")
                return False
            await websocket.accept()
            self._connections.add(websocket)
            if project_id is not None:
                self._project_connections.setdefault(project_id, set()).add(websocket)
            log.info(
                "WebSocket connection accepted",
                user_id=payload.get("sub"),
                username=payload.get("username"),
                project_id=project_id,
                total_connections=len(self._connections),
            )
            return True
        except TokenExpiredError:
            log.warning("WebSocket connection rejected: token expired")
            await websocket.close(code=1008, reason="Token expired")
            return False
        except InvalidTokenError as e:
            log.warning("WebSocket connection rejected: invalid token", error=str(e))
            await websocket.close(code=1008, reason="Invalid token")
            return False

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the manager.

        Args:
            websocket: The WebSocket connection to remove.
        """
        self._connections.discard(websocket)
        empty_projects: list[int] = []
        for project_id, connections in self._project_connections.items():
            connections.discard(websocket)
            if not connections:
                empty_projects.append(project_id)
        for project_id in empty_projects:
            del self._project_connections[project_id]
        log.debug(
            "WebSocket disconnected",
            total_connections=len(self._connections),
        )

    async def broadcast(self, message: dict[str, Any], project_id: int | None = None) -> None:
        """Broadcast a message to all connected clients.

        Handles disconnected clients gracefully by removing them
        from the connection set.

        Args:
            message: JSON-serializable message to send.
        """
        connections = self._connections if project_id is None else self._project_connections.get(project_id, set())
        if not connections:
            return

        disconnected: set[WebSocket] = set()

        for websocket in set(connections):
            try:
                await websocket.send_json(message)
            except Exception as e:
                log.debug("Failed to send to WebSocket, marking as disconnected", error=str(e))
                disconnected.add(websocket)

        # Remove disconnected clients
        for websocket in disconnected:
            await self.disconnect(websocket)

        if disconnected:
            log.debug(
                "Removed disconnected WebSocket clients",
                removed_count=len(disconnected),
                remaining_connections=len(self._connections),
            )

    async def broadcast_queue_updated(
        self,
        queue: list[dict[str, Any]],
        stats: dict[str, Any],
        project_id: int | None = None,
    ) -> None:
        """Broadcast full queue state update to all clients.

        Args:
            queue: List of MR items with positions.
            stats: Queue statistics.
        """
        await self.broadcast(
            {
                "type": "queue:updated",
                "data": {
                    "project_id": project_id,
                    "queue": queue,
                    "stats": stats,
                },
            },
            project_id,
        )

    async def broadcast_mr_status_changed(
        self,
        mr_iid: int,
        old_status: str,
        new_status: str,
        project_id: int | None = None,
    ) -> None:
        """Broadcast MR status change to all clients.

        Args:
            mr_iid: The MR's internal ID.
            old_status: Previous status.
            new_status: New status.
        """
        log.debug(
            "Broadcasting MR status change",
            mr_iid=mr_iid,
            old_status=old_status,
            new_status=new_status,
        )
        await self.broadcast(
            {
                "type": "mr:status_changed",
                "data": {
                    "project_id": project_id,
                    "iid": mr_iid,
                    "oldStatus": old_status,
                    "newStatus": new_status,
                },
            },
            project_id,
        )

    async def broadcast_mr_completed(
        self,
        mr_iid: int,
        status: str,
        finished_at: datetime | None = None,
        failure_reason: str | None = None,
        project_id: int | None = None,
    ) -> None:
        """Broadcast MR completion event to all clients.

        Args:
            mr_iid: The MR's internal ID.
            status: Final status (merged, failed, removed).
            finished_at: Completion timestamp.
            failure_reason: Error message if failed.
        """
        log.debug(
            "Broadcasting MR completion",
            mr_iid=mr_iid,
            status=status,
        )
        await self.broadcast(
            {
                "type": "mr:completed",
                "data": {
                    "project_id": project_id,
                    "iid": mr_iid,
                    "status": status,
                    "finishedAt": (finished_at or datetime.now(UTC)).isoformat(),
                    "failureReason": failure_reason,
                },
            },
            project_id,
        )


# =============================================================================
# WebSocket Router
# =============================================================================

ws_router = APIRouter(tags=["websocket"])


@ws_router.websocket("/ws/queue")
async def websocket_queue_updates(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time queue updates.

    Clients connect with JWT token as query parameter:
        ws://host:port/ws/queue?token=<jwt_token>

    On successful connection, the client receives:
    1. Initial queue state (queue:updated event)
    2. Real-time updates as MRs change status

    Events sent to clients:
    - queue:updated: Full queue state with stats
    - mr:status_changed: Single MR status transition
    - mr:completed: MR finished processing (merged/failed/removed)

    Connection will be closed with code 1008 if:
    - Token is missing
    - Token is expired
    - Token is invalid

    Args:
        websocket: The WebSocket connection.
    """
    # Import here to avoid circular imports
    from gitlab_queue.webhooks.router import WebhookAppState  # noqa: TC001

    state: WebhookAppState = websocket.app.state.webhook_state
    configured_ids = (
        sorted(state.project_components) if state.project_components else [state.settings.gitlab_project_id]
    )
    configured_ids = [project_id for project_id in configured_ids if project_id is not None]
    if len(configured_ids) != 1:
        await websocket.close(code=1008, reason="Project must be specified")
        return
    await _serve_project_queue(websocket, configured_ids[0])


@ws_router.websocket("/ws/projects/{project_id}/queue")
async def websocket_project_queue_updates(websocket: WebSocket, project_id: int) -> None:
    """Stream queue events for one configured and authorized project."""
    from gitlab_queue.webhooks.router import WebhookAppState  # noqa: TC001

    state: WebhookAppState = websocket.app.state.webhook_state
    configured_ids = set(state.project_components) if state.project_components else {state.settings.gitlab_project_id}
    if project_id not in configured_ids:
        await websocket.close(code=1008, reason="Unknown project")
        return
    await _serve_project_queue(websocket, project_id)


async def _serve_project_queue(websocket: WebSocket, project_id: int) -> None:
    """Accept and serve a WebSocket scoped to one project."""
    from gitlab_queue.webhooks.router import WebhookAppState  # noqa: TC001

    state: WebhookAppState = websocket.app.state.webhook_state
    manager = state.websocket_manager
    token = websocket.query_params.get("token")

    if not await manager.connect(websocket, token, state.settings, project_id):
        return

    try:
        # Send initial queue state
        queue_manager = state.queue_manager
        queue_items = await queue_manager.get_active_queue(project_id)
        stats = await queue_manager.get_queue_stats(project_id)

        # Convert queue items to dicts
        queue_data = []
        for i, item in enumerate(queue_items, start=1):
            queue_data.append(_queue_item_to_dict(item, position=i))

        await websocket.send_json(
            {
                "type": "queue:updated",
                "data": {
                    "project_id": project_id,
                    "queue": queue_data,
                    "stats": stats,
                },
            }
        )

        # Keep connection alive
        while True:
            # Wait for client messages (ping/pong or close)
            await websocket.receive_text()

    except WebSocketDisconnect:
        log.debug("WebSocket client disconnected normally")
    except Exception as e:
        log.warning("WebSocket error", error=str(e))
    finally:
        await manager.disconnect(websocket)


def _queue_item_to_dict(item: QueueItem, position: int | None = None) -> dict[str, Any]:
    """Convert QueueItem to dict for WebSocket response.

    Args:
        item: The queue item to serialize.
        position: Position in queue (optional).

    Returns:
        Dict suitable for JSON serialization.
    """
    result: dict[str, Any] = {
        "mr_iid": item.mr_iid,
        "project_id": item.project_id,
        "title": item.title,
        "author": {
            "name": item.author_name,
            "username": item.author_username,
            "avatar_url": item.author_avatar,
        },
        "target_branch": item.target_branch,
        "status": item.state,
        "is_hotfix": item.is_hotfix,
        "labels": item.labels,
        "queued_at": item.queued_at.isoformat(),
        "started_at": item.started_at.isoformat() if item.started_at else None,
    }

    if position is not None:
        result["position"] = position

    if item.pipeline_id is not None:
        result["pipeline"] = {
            "id": item.pipeline_id,
            "status": item.pipeline_status,
        }

    if item.last_error:
        result["last_error"] = item.last_error
        result["retry_count"] = item.get_max_job_retry_count()

    return result


__all__: list[str] = [
    "WebSocketManager",
    "ws_router",
]
