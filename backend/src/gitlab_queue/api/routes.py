"""REST API routes for GitLab Merge Queue Bot dashboard.

Provides History and Analytics endpoints for the dashboard frontend.
These endpoints are read-only and protected by authentication middleware.

Example:
    >>> from gitlab_queue.api.routes import history_router, analytics_router
    >>> app.include_router(history_router)
    >>> app.include_router(analytics_router)
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query, Request

from gitlab_queue.api.project_access import (
    authorized_project_ids_from_user,
    configured_project_ids,
    resolve_project_components,
    resolve_request_project,
)
from gitlab_queue.api.schemas import (
    dump_analytics_summary,
    dump_failure_reasons,
    dump_history_item,
    dump_hourly_analytics,
    dump_outcomes,
    dump_paginated_history,
)
from gitlab_queue.clients.gitlab import GitLabAPIError, GitLabCircuitOpenError
from gitlab_queue.db.repositories import ModelConverter, UnitOfWork
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.webhooks.router import WebhookAppState

log = get_logger(__name__)


def _create_uow(state: WebhookAppState, project_id: int) -> UnitOfWork:
    """Create a UnitOfWork using state's uow_factory if available, otherwise default.

    Args:
        state: Application state with optional uow_factory.

    Returns:
        UnitOfWork context manager instance.
    """
    if state.uow_factory is not None:
        return state.uow_factory(state.database, project_id)
    return UnitOfWork(state.database, project_id=project_id)


# =============================================================================
# History API Router
# =============================================================================

history_router = APIRouter(prefix="/api/history", tags=["history"])
projects_router = APIRouter(prefix="/api/projects", tags=["projects"])


@history_router.get("")
@projects_router.get("/{project_id}/history")
async def get_history(
    request: Request,
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    status: str | None = Query(default=None, description="Filter by status (merged, failed, conflict, timeout)"),
    date_from: date | None = Query(default=None, description="Filter from date (inclusive)"),
    date_to: date | None = Query(default=None, description="Filter to date (inclusive)"),
    search: str | None = Query(default=None, description="Search by title, author, or MR IID"),
) -> dict[str, Any]:
    """Get paginated history of completed merge requests.

    Args:
        request: FastAPI request object.
        page: Page number (1-indexed, default: 1).
        per_page: Items per page (default: 20, max: 100).
        status: Filter by final status.
        date_from: Filter MRs finished on or after this date.
        date_to: Filter MRs finished on or before this date.
        search: Search term for title, author username, or MR IID.

    Returns:
        Dict with history items and pagination metadata.
    """
    state: WebhookAppState = request.app.state.webhook_state
    project_id = resolve_request_project(request, state)

    async with _create_uow(state, project_id) as uow:
        # Get paginated history with filters
        result = await uow.history.get_history(
            page=page,
            per_page=per_page,
            status_filter=status,
            date_from=date_from,
            date_to=date_to,
        )

        # Convert to QueueItems for consistent response format
        items = [ModelConverter.history_model_to_queue_item(h) for h in result.items]

        # Apply search filter if provided (in-memory for simplicity)
        if search:
            search_lower = search.lower()
            items = [
                item
                for item in items
                if search_lower in item.title.lower()
                or search_lower in item.author_username.lower()
                or search_lower in item.author_name.lower()
                or search_lower == str(item.mr_iid)
            ]

    return dump_paginated_history(
        items=items,
        page=result.page,
        per_page=result.per_page,
        total=result.total,
        total_pages=result.total_pages,
    )


@history_router.get("/{iid}")
@projects_router.get("/{project_id}/history/{iid}")
async def get_history_item(request: Request, iid: int) -> dict[str, Any]:
    """Get a specific MR from history by its IID.

    Args:
        request: FastAPI request object.
        iid: The MR's internal ID.

    Returns:
        Dict with MR history details.

    Raises:
        HTTPException: 404 if MR not found in history.
    """
    state: WebhookAppState = request.app.state.webhook_state
    project_id = resolve_request_project(request, state)

    async with _create_uow(state, project_id) as uow:
        item = await uow.history.get_by_iid(iid)
        if item is None:
            raise HTTPException(status_code=404, detail=f"MR !{iid} not found in history")

        queue_item = ModelConverter.history_model_to_queue_item(item)
        return dump_history_item(queue_item)


# =============================================================================
# Analytics API Router
# =============================================================================

analytics_router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@analytics_router.get("/summary")
@projects_router.get("/{project_id}/analytics/summary")
async def get_analytics_summary(
    request: Request,
    days: int = Query(default=7, ge=1, le=365, description="Number of days to include"),
) -> dict[str, Any]:
    """Get summary analytics for the specified period.

    Args:
        request: FastAPI request object.
        days: Number of days to include in statistics (default: 7).

    Returns:
        Dict with aggregate statistics.
    """
    state: WebhookAppState = request.app.state.webhook_state
    project_id = resolve_request_project(request, state)

    now = datetime.now(UTC)
    date_from = (now - timedelta(days=days)).date()
    date_to = now.date()

    async with _create_uow(state, project_id) as uow:
        stats = await uow.history.get_stats_for_period(date_from, date_to)

    total_processed = stats.total_processed
    success_rate = (stats.success_count / total_processed * 100) if total_processed > 0 else 0.0
    daily_throughput = total_processed / days if days > 0 else 0.0

    return dump_analytics_summary(
        total_processed=total_processed,
        avg_wait_time_seconds=stats.avg_wait_time_seconds or 0,
        avg_processing_time_seconds=stats.avg_processing_time_seconds or 0,
        success_rate_percent=round(success_rate, 1),
        daily_throughput=round(daily_throughput, 1),
        period_days=days,
    )


@analytics_router.get("/hourly")
@projects_router.get("/{project_id}/analytics/hourly")
async def get_hourly_analytics(
    request: Request,
    hours: int = Query(default=24, ge=1, le=168, description="Number of hours to include (max 168 = 7 days)"),
) -> dict[str, Any]:
    """Get hourly analytics data points.

    Args:
        request: FastAPI request object.
        hours: Number of hours to include (default: 24, max: 168).

    Returns:
        Dict with hourly data points.
    """
    state: WebhookAppState = request.app.state.webhook_state
    project_id = resolve_request_project(request, state)

    # Convert hours to days for get_metrics (round up)
    period_days = (hours + 23) // 24

    async with _create_uow(state, project_id) as uow:
        metrics = await uow.analytics.get_metrics(period_days)

    # Filter hourly_trend to requested hours
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    cutoff_str = cutoff.isoformat()

    filtered_data = [point for point in metrics.hourly_trend if point["timestamp"] >= cutoff_str]

    return dump_hourly_analytics(data=filtered_data, hours=hours)


@analytics_router.get("/outcomes")
@projects_router.get("/{project_id}/analytics/outcomes")
async def get_outcomes_analytics(
    request: Request,
    days: int = Query(default=7, ge=1, le=365, description="Number of days to include"),
) -> dict[str, Any]:
    """Get outcome breakdown for the specified period.

    Args:
        request: FastAPI request object.
        days: Number of days to include (default: 7).

    Returns:
        Dict with outcome breakdown (success, failed, conflict, timeout).
    """
    state: WebhookAppState = request.app.state.webhook_state
    project_id = resolve_request_project(request, state)

    now = datetime.now(UTC)
    date_from = (now - timedelta(days=days)).date()
    date_to = now.date()

    async with _create_uow(state, project_id) as uow:
        stats = await uow.history.get_stats_for_period(date_from, date_to)

    total = stats.total_processed or 1  # Avoid division by zero

    outcomes: list[dict[str, Any]] = [
        {
            "name": "merged",
            "count": stats.success_count,
            "percentage": round(stats.success_count / total * 100, 1),
        },
        {
            "name": "failed",
            "count": stats.failed_count,
            "percentage": round(stats.failed_count / total * 100, 1),
        },
        {
            "name": "conflict",
            "count": stats.conflict_count,
            "percentage": round(stats.conflict_count / total * 100, 1),
        },
        {
            "name": "timeout",
            "count": stats.timeout_count,
            "percentage": round(stats.timeout_count / total * 100, 1),
        },
    ]

    # Filter out zero-count outcomes for cleaner response
    outcomes = [o for o in outcomes if int(o["count"]) > 0]

    return dump_outcomes(outcomes=outcomes, total=stats.total_processed, period_days=days)


@analytics_router.get("/failure-reasons")
@projects_router.get("/{project_id}/analytics/failure-reasons")
async def get_failure_reasons(
    request: Request,
    days: int = Query(default=7, ge=1, le=365, description="Number of days to include"),
) -> dict[str, Any]:
    """Get failure reason breakdown for the specified period.

    Args:
        request: FastAPI request object.
        days: Number of days to include (default: 7).

    Returns:
        Dict with failure reason breakdown.
    """
    state: WebhookAppState = request.app.state.webhook_state
    project_id = resolve_request_project(request, state)

    now = datetime.now(UTC)
    date_from = (now - timedelta(days=days)).date()
    date_to = now.date()

    async with _create_uow(state, project_id) as uow:
        # Get failure reasons from history
        result = await uow.history.get_history(
            page=1,
            per_page=1000,  # Get all for aggregation
            date_from=date_from,
            date_to=date_to,
        )

        # Aggregate failure reasons (must be inside session context)
        reason_counts: dict[str, int] = {}
        for item in result.items:
            if item.status in ("failed", "conflict", "timeout"):
                reason = item.failure_reason or item.status
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

    total_failures = sum(reason_counts.values()) or 1  # Avoid division by zero

    reasons = [
        {
            "reason": reason,
            "count": count,
            "percentage": round(count / total_failures * 100, 1),
        }
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1])
    ]

    return dump_failure_reasons(
        reasons=reasons,
        total_failures=sum(reason_counts.values()),
        period_days=days,
    )


# =============================================================================
# Config API Router
# =============================================================================

config_router = APIRouter(prefix="/api/config", tags=["config"])


@config_router.get("")
@projects_router.get("/{project_id}/config")
async def get_config(request: Request) -> dict[str, str]:
    """Get project configuration.

    Returns:
        Dict with project_web_url from GitLab API.

    Raises:
        HTTPException: 503 if GitLab API is unavailable.
    """
    state: WebhookAppState = request.app.state.webhook_state
    project_id = resolve_request_project(request, state)
    components = resolve_project_components(state, project_id)
    gitlab_client = components.gitlab_client if components else state.gitlab_client
    try:
        project_web_url = await gitlab_client.get_project_web_url()
    except GitLabCircuitOpenError as e:
        retry_after = int(e.retry_after or 30)
        raise HTTPException(
            status_code=503,
            detail="GitLab API temporarily unavailable",
            headers={"Retry-After": str(retry_after)},
        )
    except GitLabAPIError as e:
        log.warning("Failed to fetch project config from GitLab", error=str(e))
        raise HTTPException(
            status_code=503,
            detail="Failed to fetch project configuration from GitLab",
        )
    return {"project_web_url": project_web_url}


@projects_router.get("")
async def get_projects(request: Request) -> dict[str, list[dict[str, Any]]]:
    """List configured projects visible to the authenticated user."""
    state: WebhookAppState = request.app.state.webhook_state
    allowed_ids = authorized_project_ids_from_user(getattr(request.state, "user", None))
    projects: list[dict[str, Any]] = []

    for project_id in configured_project_ids(state):
        if project_id not in allowed_ids:
            continue
        components = resolve_project_components(state, project_id)
        gitlab_client = components.gitlab_client if components else state.gitlab_client
        try:
            web_url = await gitlab_client.get_project_web_url()
        except (GitLabAPIError, GitLabCircuitOpenError):
            web_url = ""
        project_path = urlsplit(web_url).path.strip("/") if web_url else ""
        name = project_path or f"Project {project_id}"
        projects.append({"project_id": project_id, "web_url": web_url, "name": name})

    return {"projects": projects}


# =============================================================================
# Exports
# =============================================================================

__all__: list[str] = [
    "analytics_router",
    "config_router",
    "history_router",
    "projects_router",
]
