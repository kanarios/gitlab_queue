"""Schemas for MergeRequest and Note from src/gitlab_queue/models/mr.py."""

from d42 import optional, schema

from scenarios.library import MRState
from scenarios.schemas._helpers import enum_schema
from scenarios.schemas.author import AuthorSchema
from scenarios.schemas.constants import MAX_LABELS

# Schema for MR state enum
MRStateSchema = enum_schema(MRState)

# Corresponds to dataclass MergeRequest
MergeRequestSchema = schema.dict(
    {
        "iid": schema.int.min(1).max(2_147_483_647),
        "title": schema.str.len(1, 255),
        "state": MRStateSchema,
        "labels": schema.list(schema.str.len(1, 255)).len(0, MAX_LABELS),
        "sha": schema.str.regex(r"^[a-f0-9]{40}$"),
        "source_branch": schema.str.len(1, 255),
        "target_branch": schema.str.len(1, 255),
        "merge_status": schema.str.len(1, 50),
        "author": AuthorSchema,
        optional("has_conflicts"): schema.bool,
        optional("rebase_in_progress"): schema.bool,
        optional("web_url"): schema.str.len(1, 2048),
    }
)

# Corresponds to dataclass Note
NoteSchema = schema.dict(
    {
        "id": schema.int.min(1).max(2_147_483_647),
        "body": schema.str.len(1, 10_000),  # Markdown content
        "author": AuthorSchema,
        optional("system"): schema.bool,
    }
)

__all__ = [
    "MRStateSchema",
    "MergeRequestSchema",
    "NoteSchema",
]
