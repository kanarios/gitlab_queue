"""Schemas for Pipeline webhook events from src/gitlab_queue/models/events.py."""

from d42 import optional, schema

from scenarios.schemas.constants import DATETIME_PATTERN

# Pipeline statuses from GitLab
PIPELINE_STATUSES = [
    "pending",
    "running",
    "success",
    "failed",
    "canceled",
    "skipped",
    "manual",
    "scheduled",
]
PipelineStatusSchema = schema.any(*[schema.str(s) for s in PIPELINE_STATUSES])

# Corresponds to dataclass PipelineAttributes
PipelineAttributesSchema = schema.dict(
    {
        "id": schema.int.min(1).max(2_147_483_647),
        "status": PipelineStatusSchema,
        "sha": schema.str.regex(r"^[a-f0-9]{40}$"),
        "ref": schema.str.len(1, 255),
        optional("web_url"): schema.str.len(1, 2048),
        optional("created_at"): schema.str.regex(DATETIME_PATTERN),
    }
)

# Corresponds to dataclass PipelineEvent
PipelineEventSchema = schema.dict(
    {
        "object_kind": schema.str("pipeline"),
        "project_id": schema.int.min(1).max(2_147_483_647),
        "object_attributes": PipelineAttributesSchema,
        optional("merge_request_iid"): schema.int.min(1).max(2_147_483_647),
    }
)

__all__ = [
    "PIPELINE_STATUSES",
    "PipelineAttributesSchema",
    "PipelineEventSchema",
    "PipelineStatusSchema",
]
