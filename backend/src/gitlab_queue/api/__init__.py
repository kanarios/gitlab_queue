"""REST API module for GitLab Merge Queue Bot.

Provides History, Analytics, and WebSocket API endpoints for the dashboard.
"""

from gitlab_queue.api.routes import analytics_router, config_router, history_router
from gitlab_queue.api.schemas import (
    AnalyticsSummarySchema,
    AuthorSchema,
    FailureReasonSchema,
    FailureReasonsResponse,
    HistoryItemSchema,
    HourlyAnalyticsResponse,
    HourlyDataPointSchema,
    OutcomeSchema,
    OutcomesResponse,
    PaginatedHistoryResponse,
    PaginationSchema,
    PipelineInfoSchema,
    api_retort,
    dump_analytics_summary,
    dump_failure_reasons,
    dump_history_item,
    dump_hourly_analytics,
    dump_outcomes,
    dump_paginated_history,
)
from gitlab_queue.api.websocket import WebSocketManager, ws_router

__all__: list[str] = [
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
    "WebSocketManager",
    "analytics_router",
    "api_retort",
    "config_router",
    "dump_analytics_summary",
    "dump_failure_reasons",
    "dump_history_item",
    "dump_hourly_analytics",
    "dump_outcomes",
    "dump_paginated_history",
    "history_router",
    "ws_router",
]
