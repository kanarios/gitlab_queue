"""Schemas for MR webhook events from src/gitlab_queue/models/events.py."""

from d42 import optional, schema

from scenarios.library import MRState
from scenarios.schemas._helpers import enum_schema
from scenarios.schemas.constants import MAX_LABELS

MRStateSchema = enum_schema(MRState)

# MR actions from GitLab webhooks
MR_ACTIONS = [
    "open",
    "close",
    "reopen",
    "update",
    "merge",
    "approved",
    "unapproved",
    "labeled",
    "unlabeled",
]
MRActionSchema = schema.any(*[schema.str(a) for a in MR_ACTIONS])

# Corresponds to dataclass LabelChanges
LabelChangesSchema = schema.dict(
    {
        optional("previous"): schema.list(schema.str.len(1, 255)).len(0, MAX_LABELS),
        optional("current"): schema.list(schema.str.len(1, 255)).len(0, MAX_LABELS),
    }
)

# Corresponds to dataclass MergeRequestAttributes
MRAttributesSchema = schema.dict(
    {
        "iid": schema.int.min(1).max(2_147_483_647),
        "title": schema.str.len(1, 255),
        "state": MRStateSchema,
        "action": MRActionSchema,
        "source_branch": schema.str.len(1, 255),
        "target_branch": schema.str.len(1, 255),
        "merge_status": schema.str.len(1, 50),
        optional("sha"): schema.str.regex(r"^[a-f0-9]{40}$"),
        optional("has_conflicts"): schema.bool,
        optional("rebase_in_progress"): schema.bool,
        optional("web_url"): schema.str.len(1, 2048),
    }
)

# Corresponds to dataclass MergeRequestEvent
MergeRequestEventSchema = schema.dict(
    {
        "object_kind": schema.str("merge_request"),
        "event_type": schema.str("merge_request"),
        "project_id": schema.int.min(1).max(2_147_483_647),
        "object_attributes": MRAttributesSchema,
        "user_id": schema.int.min(1).max(2_147_483_647),
        "user_name": schema.str.len(1, 255),
        "user_username": schema.str.len(1, 255),
        optional("user_avatar"): schema.str.len(1, 2048),
        optional("labels"): schema.list(schema.str.len(1, 255)).len(0, MAX_LABELS),
        optional("label_changes"): LabelChangesSchema,
    }
)

__all__ = [
    "MR_ACTIONS",
    "LabelChangesSchema",
    "MRActionSchema",
    "MRAttributesSchema",
    "MergeRequestEventSchema",
]
