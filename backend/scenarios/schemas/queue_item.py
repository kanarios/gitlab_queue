"""Schemas for QueueItem and DashboardStats from src/gitlab_queue/models/queue_item.py."""

from d42 import optional, schema

from scenarios.library import QueueState
from scenarios.schemas._helpers import enum_schema
from scenarios.schemas.constants import DATETIME_PATTERN, MAX_LABELS

# Schema for queue state enum
QueueStateSchema = enum_schema(QueueState)

# Corresponds to dataclass QueueItem
QueueItemSchema = schema.dict(
    {
        "mr_iid": schema.int.min(1).max(2_147_483_647),
        "title": schema.str.len(1, 255),
        "author_name": schema.str.len(1, 255),
        "author_username": schema.str.len(1, 255),
        "target_branch": schema.str.len(1, 255),
        "state": QueueStateSchema,
        "queued_at": schema.str.regex(DATETIME_PATTERN),  # ISO datetime
        optional("is_hotfix"): schema.bool,
        optional("author_avatar"): schema.str.len(1, 2048),
        optional("labels"): schema.list(schema.str.len(1, 255)).len(0, MAX_LABELS),
        optional("started_at"): schema.str.regex(DATETIME_PATTERN),
        optional("finished_at"): schema.str.regex(DATETIME_PATTERN),
        optional("pipeline_id"): schema.int.min(1).max(2_147_483_647),
        optional("pipeline_status"): schema.str.len(1, 50),
        optional("retry_count"): schema.int.min(0).max(100),
        optional("last_error"): schema.str.len(1, 10_000),
        optional("stale_warning_sent"): schema.bool,
    }
)

# Corresponds to dataclass DashboardStats
DashboardStatsSchema = schema.dict(
    {
        "total_in_queue": schema.int.min(0),
        "merged_count": schema.int.min(0),
        "failed_count": schema.int.min(0),
        "success_rate": schema.float.min(0.0).max(100.0),
        "avg_wait_seconds": schema.float.min(0.0),
        "avg_processing_seconds": schema.float.min(0.0),
        "stats_window_days": schema.int.min(1).max(365),
    }
)

__all__ = [
    "DashboardStatsSchema",
    "QueueItemSchema",
    "QueueStateSchema",
]
