"""Schemas for Note webhook events from src/gitlab_queue/models/events.py."""

from d42 import optional, schema

# Types of objects for notes
NOTEABLE_TYPES = ["MergeRequest", "Issue", "Commit", "Snippet"]
NoteableTypeSchema = schema.any(*[schema.str(t) for t in NOTEABLE_TYPES])

# Corresponds to dataclass NoteEvent
NoteEventSchema = schema.dict(
    {
        "object_kind": schema.str("note"),
        "event_type": schema.str("note"),
        "project_id": schema.int.min(1).max(2_147_483_647),
        "user_id": schema.int.min(1).max(2_147_483_647),
        "user_name": schema.str.len(1, 255),
        "user_username": schema.str.len(1, 255),
        "note_id": schema.int.min(1).max(2_147_483_647),
        "note_body": schema.str.len(1, 10_000),
        "noteable_type": NoteableTypeSchema,
        optional("merge_request_iid"): schema.int.min(1).max(2_147_483_647),
    }
)

__all__ = [
    "NOTEABLE_TYPES",
    "NoteEventSchema",
    "NoteableTypeSchema",
]
