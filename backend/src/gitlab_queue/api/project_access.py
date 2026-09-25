"""Project selection and authorization helpers for HTTP and WebSocket APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

from gitlab_queue.auth.jwt_handler import get_authorized_project_ids

if TYPE_CHECKING:
    from fastapi import Request

    from gitlab_queue.core.project_components import ProjectComponents
    from gitlab_queue.webhooks.router import WebhookAppState


def configured_project_ids(state: WebhookAppState) -> tuple[int, ...]:
    """Return configured project IDs in stable configuration order."""
    components = state.project_components
    if components:
        return tuple(components)
    return tuple(project.project_id for project in state.settings.projects)


def authorized_project_ids_from_user(user: dict[str, Any] | None) -> frozenset[int]:
    """Return project IDs from middleware user data or decoded JWT claims."""
    if user is None:
        return frozenset()
    return get_authorized_project_ids(user)


def resolve_project_id(
    request: Request,
    state: WebhookAppState,
    requested_project_id: int | None,
) -> int:
    """Resolve and authorize a project for a REST request.

    Legacy endpoints without a project ID remain available only when exactly
    one project is configured. A missing or unauthorized ID is deliberately
    reported as 404 so configured project membership is not disclosed.
    """
    configured_ids = configured_project_ids(state)
    if requested_project_id is None:
        if len(configured_ids) != 1:
            raise HTTPException(
                status_code=400,
                detail="project_id is required when multiple projects are configured",
            )
        requested_project_id = configured_ids[0]

    if requested_project_id not in configured_ids:
        raise HTTPException(status_code=404, detail="Project not found")

    user = getattr(request.state, "user", None)
    if requested_project_id not in authorized_project_ids_from_user(user):
        raise HTTPException(status_code=404, detail="Project not found")
    return requested_project_id


def resolve_project_components(
    state: WebhookAppState,
    project_id: int,
) -> ProjectComponents | None:
    """Return runtime components for a configured project when available."""
    components = state.project_components
    if components:
        return components.get(project_id)
    return None


__all__ = [
    "authorized_project_ids_from_user",
    "configured_project_ids",
    "resolve_project_components",
    "resolve_project_id",
]
