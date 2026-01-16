"""API response schemas for GitLab Merge Queue Bot.

Provides typed dataclass schemas and Adaptix retort for consistent,
type-safe API response serialization.

Example:
    >>> from gitlab_queue.api.schemas import dump_history_item, dump_paginated_history
    >>> item_dict = dump_history_item(queue_item)
    >>> response = dump_paginated_history(items, pagination)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from adaptix import Retort

if TYPE_CHECKING:
    from gitlab_queue.models.queue_item import QueueItem


# =============================================================================
# Base Schemas
# =============================================================================


@dataclass(frozen=True, slots=True)
class AuthorSchema:
    """Author information schema."""

    name: str
    username: str
    avatar_url: str | None


@dataclass(frozen=True, slots=True)
class PipelineInfoSchema:
    """Pipeline information schema."""

    id: int
    status: str | None


@dataclass(frozen=True, slots=True)
class PaginationSchema:
    """Pagination metadata schema."""

    page: int
    per_page: int
    total: int
    total_pages: int


# =============================================================================
# History Schemas
# =============================================================================


@dataclass(frozen=True, slots=True)
class HistoryItemSchema:
    """History item schema for a completed MR."""

    mr_iid: int
    title: str
    author: AuthorSchema
    target_branch: str
    status: str
    is_hotfix: bool
    labels: list[str]
    queued_at: str
    started_at: str | None
    finished_at: str | None
    pipeline: PipelineInfoSchema | None
    failure_reason: str | None


@dataclass(frozen=True, slots=True)
class PaginatedHistoryResponse:
    """Paginated history response schema."""

    items: list[HistoryItemSchema]
    pagination: PaginationSchema


# =============================================================================
# Analytics Schemas
# =============================================================================


@dataclass(frozen=True, slots=True)
class AnalyticsSummarySchema:
    """Analytics summary statistics schema."""

    total_processed: int
    avg_wait_time_seconds: float
    avg_processing_time_seconds: float
    success_rate_percent: float
    daily_throughput: float
    period_days: int


@dataclass(frozen=True, slots=True)
class HourlyDataPointSchema:
    """Hourly analytics data point schema."""

    timestamp: str
    queue_depth: int
    processed_count: int


@dataclass(frozen=True, slots=True)
class HourlyAnalyticsResponse:
    """Hourly analytics response schema."""

    data: list[HourlyDataPointSchema]
    hours: int


@dataclass(frozen=True, slots=True)
class OutcomeSchema:
    """Outcome breakdown item schema."""

    name: str
    count: int
    percentage: float


@dataclass(frozen=True, slots=True)
class OutcomesResponse:
    """Outcomes breakdown response schema."""

    outcomes: list[OutcomeSchema]
    total: int
    period_days: int


@dataclass(frozen=True, slots=True)
class FailureReasonSchema:
    """Failure reason item schema."""

    reason: str
    count: int
    percentage: float


@dataclass(frozen=True, slots=True)
class FailureReasonsResponse:
    """Failure reasons response schema."""

    reasons: list[FailureReasonSchema]
    total_failures: int
    period_days: int


# =============================================================================
# Adaptix Retort
# =============================================================================

api_retort = Retort()


# =============================================================================
# Serialization Functions
# =============================================================================


def _build_history_item_schema(item: QueueItem) -> HistoryItemSchema:
    """Build HistoryItemSchema from QueueItem.

    Args:
        item: QueueItem to convert.

    Returns:
        HistoryItemSchema instance.
    """
    pipeline: PipelineInfoSchema | None = None
    if item.pipeline_id is not None:
        pipeline = PipelineInfoSchema(
            id=item.pipeline_id,
            status=item.pipeline_status,
        )

    return HistoryItemSchema(
        mr_iid=item.mr_iid,
        title=item.title,
        author=AuthorSchema(
            name=item.author_name,
            username=item.author_username,
            avatar_url=item.author_avatar,
        ),
        target_branch=item.target_branch,
        status=item.state,
        is_hotfix=item.is_hotfix,
        labels=item.labels,
        queued_at=item.queued_at.isoformat(),
        started_at=item.started_at.isoformat() if item.started_at else None,
        finished_at=item.finished_at.isoformat() if item.finished_at else None,
        pipeline=pipeline,
        failure_reason=item.last_error,
    )


def dump_history_item(item: QueueItem) -> dict[str, Any]:
    """Serialize QueueItem to history item dict.

    Args:
        item: QueueItem to serialize.

    Returns:
        Dictionary suitable for JSON response.
    """
    schema = _build_history_item_schema(item)
    return cast("dict[str, Any]", api_retort.dump(schema))


def dump_paginated_history(
    items: list[QueueItem],
    page: int,
    per_page: int,
    total: int,
    total_pages: int,
) -> dict[str, Any]:
    """Serialize paginated history response.

    Args:
        items: List of QueueItems to serialize.
        page: Current page number.
        per_page: Items per page.
        total: Total number of items.
        total_pages: Total number of pages.

    Returns:
        Dictionary with items and pagination metadata.
    """
    response = PaginatedHistoryResponse(
        items=[_build_history_item_schema(item) for item in items],
        pagination=PaginationSchema(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
        ),
    )
    return cast("dict[str, Any]", api_retort.dump(response))


def dump_analytics_summary(
    total_processed: int,
    avg_wait_time_seconds: float,
    avg_processing_time_seconds: float,
    success_rate_percent: float,
    daily_throughput: float,
    period_days: int,
) -> dict[str, Any]:
    """Serialize analytics summary response.

    Args:
        total_processed: Total MRs processed.
        avg_wait_time_seconds: Average wait time in seconds.
        avg_processing_time_seconds: Average processing time in seconds.
        success_rate_percent: Success rate percentage.
        daily_throughput: Average daily throughput.
        period_days: Number of days in the period.

    Returns:
        Dictionary for JSON response.
    """
    schema = AnalyticsSummarySchema(
        total_processed=total_processed,
        avg_wait_time_seconds=avg_wait_time_seconds,
        avg_processing_time_seconds=avg_processing_time_seconds,
        success_rate_percent=success_rate_percent,
        daily_throughput=daily_throughput,
        period_days=period_days,
    )
    return cast("dict[str, Any]", api_retort.dump(schema))


def dump_hourly_analytics(
    data: list[dict[str, Any]],
    hours: int,
) -> dict[str, Any]:
    """Serialize hourly analytics response.

    Args:
        data: List of hourly data points as dicts.
        hours: Number of hours in the period.

    Returns:
        Dictionary for JSON response.
    """
    response = HourlyAnalyticsResponse(
        data=[
            HourlyDataPointSchema(
                timestamp=point["timestamp"],
                queue_depth=point["queue_depth"],
                processed_count=point["processed_count"],
            )
            for point in data
        ],
        hours=hours,
    )
    return cast("dict[str, Any]", api_retort.dump(response))


def dump_outcomes(
    outcomes: list[dict[str, Any]],
    total: int,
    period_days: int,
) -> dict[str, Any]:
    """Serialize outcomes breakdown response.

    Args:
        outcomes: List of outcome dicts with name, count, percentage.
        total: Total number of items.
        period_days: Number of days in the period.

    Returns:
        Dictionary for JSON response.
    """
    response = OutcomesResponse(
        outcomes=[
            OutcomeSchema(
                name=o["name"],
                count=int(o["count"]),
                percentage=float(o["percentage"]),
            )
            for o in outcomes
        ],
        total=total,
        period_days=period_days,
    )
    return cast("dict[str, Any]", api_retort.dump(response))


def dump_failure_reasons(
    reasons: list[dict[str, Any]],
    total_failures: int,
    period_days: int,
) -> dict[str, Any]:
    """Serialize failure reasons response.

    Args:
        reasons: List of reason dicts with reason, count, percentage.
        total_failures: Total number of failures.
        period_days: Number of days in the period.

    Returns:
        Dictionary for JSON response.
    """
    response = FailureReasonsResponse(
        reasons=[
            FailureReasonSchema(
                reason=r["reason"],
                count=int(r["count"]),
                percentage=float(r["percentage"]),
            )
            for r in reasons
        ],
        total_failures=total_failures,
        period_days=period_days,
    )
    return cast("dict[str, Any]", api_retort.dump(response))


# =============================================================================
# Exports
# =============================================================================

__all__: list[str] = [
    # Schemas
    "AnalyticsSummarySchema",
    "AuthorSchema",
    "FailureReasonSchema",
    "FailureReasonsResponse",
    "HistoryItemSchema",
    "HourlyAnalyticsResponse",
    "HourlyDataPointSchema",
    "OutcomeSchema",
    "OutcomesResponse",
    "PaginatedHistoryResponse",
    "PaginationSchema",
    "PipelineInfoSchema",
    # Retort
    "api_retort",
    # Serialization functions
    "dump_analytics_summary",
    "dump_failure_reasons",
    "dump_history_item",
    "dump_hourly_analytics",
    "dump_outcomes",
    "dump_paginated_history",
]
