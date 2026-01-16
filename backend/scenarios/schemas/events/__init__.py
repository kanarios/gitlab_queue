"""Schemas for webhook events."""

from scenarios.schemas.events.mr_event import (
    MR_ACTIONS,
    LabelChangesSchema,
    MergeRequestEventSchema,
    MRActionSchema,
    MRAttributesSchema,
)
from scenarios.schemas.events.note_event import (
    NOTEABLE_TYPES,
    NoteableTypeSchema,
    NoteEventSchema,
)
from scenarios.schemas.events.pipeline_event import (
    PIPELINE_STATUSES,
    PipelineAttributesSchema,
    PipelineEventSchema,
    PipelineStatusSchema,
)

__all__ = [
    "MR_ACTIONS",
    "NOTEABLE_TYPES",
    "PIPELINE_STATUSES",
    "LabelChangesSchema",
    "MRActionSchema",
    "MRAttributesSchema",
    "MergeRequestEventSchema",
    "NoteEventSchema",
    "NoteableTypeSchema",
    "PipelineAttributesSchema",
    "PipelineEventSchema",
    "PipelineStatusSchema",
]
