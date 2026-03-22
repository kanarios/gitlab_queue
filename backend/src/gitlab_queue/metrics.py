"""Prometheus metrics for GitLab Merge Queue Bot.

Provides metrics collection for monitoring queue operations, GitLab API
performance, and system health.

Example:
    >>> from gitlab_queue.metrics import OPERATIONS_TOTAL, API_LATENCY
    >>> OPERATIONS_TOTAL.labels(type="add", status="success").inc()
    >>> with API_LATENCY.labels(method="GET", endpoint="/merge_requests").time():
    ...     await client.get_mr(42)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

if TYPE_CHECKING:
    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.core.queue import QueueManager

# Export content type for /metrics endpoint
METRICS_CONTENT_TYPE = CONTENT_TYPE_LATEST

# =============================================================================
# Queue Metrics
# =============================================================================

QUEUE_LENGTH = Gauge(
    "merge_queue_length",
    "Current number of MRs in queue by status",
    ["status"],
)

MR_DURATION = Histogram(
    "merge_queue_mr_duration_seconds",
    "Time from queued to finished for MRs",
    ["result"],
    buckets=[60, 300, 600, 1800, 3600, 7200],  # 1m, 5m, 10m, 30m, 1h, 2h
)

OPERATIONS_TOTAL = Counter(
    "merge_queue_operations_total",
    "Total queue operations by type and status",
    ["type", "status"],
)

# =============================================================================
# GitLab API Metrics
# =============================================================================

API_LATENCY = Histogram(
    "merge_queue_gitlab_api_latency_seconds",
    "GitLab API request latency by method and endpoint",
    ["method", "endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

RATE_LIMIT_REMAINING = Gauge(
    "merge_queue_rate_limit_remaining",
    "GitLab API rate limit remaining requests",
)

CIRCUIT_BREAKER_STATE = Gauge(
    "merge_queue_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=half_open, 2=open)",
)


# =============================================================================
# Helper Functions
# =============================================================================


def get_metrics_output() -> bytes:
    """Generate Prometheus metrics output in text format.

    Returns:
        Prometheus text format metrics data.
    """
    return generate_latest()


async def update_queue_metrics(queue_manager: QueueManager, project_id: int) -> None:
    """Update queue length metrics from queue manager.

    Fetches current queue stats and updates the QUEUE_LENGTH gauge
    for each status.

    Args:
        queue_manager: Queue manager instance to get stats from.
        project_id: GitLab project ID.
    """
    stats = await queue_manager.get_queue_stats(project_id)
    for status, count in stats.items():
        QUEUE_LENGTH.labels(status=status).set(count)


def update_gitlab_metrics(gitlab_client: GitLabClient) -> None:
    """Update GitLab-related metrics from client state.

    Updates rate limit and circuit breaker state metrics.

    Args:
        gitlab_client: GitLab client instance.
    """
    # Rate limit remaining (default to 0 if unknown)
    rate_limit = gitlab_client.rate_limit_state
    RATE_LIMIT_REMAINING.set(rate_limit.remaining if rate_limit.remaining is not None else 0)

    # Circuit breaker state: 0=closed, 1=half_open, 2=open
    cb = gitlab_client.circuit_breaker
    state_map = {"closed": 0, "half_open": 1, "open": 2}
    CIRCUIT_BREAKER_STATE.set(state_map.get(cb.state.value, -1))


def normalize_endpoint(endpoint: str) -> str:
    """Normalize endpoint path for metric labels.

    Replaces numeric IDs with placeholders to prevent high cardinality.

    Args:
        endpoint: Raw API endpoint path.

    Returns:
        Normalized endpoint path.

    Example:
        >>> normalize_endpoint("/projects/123/merge_requests/42")
        '/projects/:id/merge_requests/:iid'
    """
    import re

    # Replace numeric path segments with placeholders
    # /projects/123 -> /projects/:id
    # /merge_requests/42 -> /merge_requests/:iid
    normalized = re.sub(r"/projects/\d+", "/projects/:id", endpoint)
    normalized = re.sub(r"/merge_requests/\d+", "/merge_requests/:iid", normalized)
    normalized = re.sub(r"/pipelines/\d+", "/pipelines/:id", normalized)
    normalized = re.sub(r"/jobs/\d+", "/jobs/:id", normalized)
    normalized = re.sub(r"/notes/\d+", "/notes/:id", normalized)
    return normalized


__all__ = [
    "API_LATENCY",
    "CIRCUIT_BREAKER_STATE",
    "METRICS_CONTENT_TYPE",
    "MR_DURATION",
    "OPERATIONS_TOTAL",
    "QUEUE_LENGTH",
    "RATE_LIMIT_REMAINING",
    "get_metrics_output",
    "normalize_endpoint",
    "update_gitlab_metrics",
    "update_queue_metrics",
]
