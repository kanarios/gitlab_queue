"""d42 schemas for test data."""

# Utilities
from scenarios.schemas._helpers import enum_schema

# Base schemas
from scenarios.schemas.author import AuthorSchema

# Constants
from scenarios.schemas.constants import DATETIME_PATTERN, MAX_LABELS, SHA_LENGTH

# Events
from scenarios.schemas.events import (
    MR_ACTIONS,
    NOTEABLE_TYPES,
    PIPELINE_STATUSES,
    LabelChangesSchema,
    MergeRequestEventSchema,
    MRActionSchema,
    MRAttributesSchema,
    NoteableTypeSchema,
    NoteEventSchema,
    PipelineAttributesSchema,
    PipelineEventSchema,
    PipelineStatusSchema,
)
from scenarios.schemas.merge_request import (
    MergeRequestSchema,
    MRStateSchema,
    NoteSchema,
)
from scenarios.schemas.queue_item import (
    DashboardStatsSchema,
    QueueItemSchema,
    QueueStateSchema,
)
from scenarios.schemas.secret import (
    GitLabTokenSchema,
    JWTSecretSchema,
    SecretValueSchema,
    WebhookSecretSchema,
)
from scenarios.schemas.status_code import (
    AcceptedStatusSchema,
    BadRequestStatusSchema,
    ConflictStatusSchema,
    CreatedStatusSchema,
    ForbiddenStatusSchema,
    InternalServerErrorStatusSchema,
    NoContentStatusSchema,
    NotFoundStatusSchema,
    OkStatusSchema,
    ServiceUnavailableStatusSchema,
    UnauthorizedStatusSchema,
    UnprocessableEntityStatusSchema,
)

__all__ = [
    "DATETIME_PATTERN",
    "MAX_LABELS",
    "MR_ACTIONS",
    "NOTEABLE_TYPES",
    "PIPELINE_STATUSES",
    "SHA_LENGTH",
    "AcceptedStatusSchema",
    "AuthorSchema",
    "BadRequestStatusSchema",
    "ConflictStatusSchema",
    "CreatedStatusSchema",
    "DashboardStatsSchema",
    "ForbiddenStatusSchema",
    "GitLabTokenSchema",
    "InternalServerErrorStatusSchema",
    "JWTSecretSchema",
    "LabelChangesSchema",
    "MRActionSchema",
    "MRAttributesSchema",
    "MRStateSchema",
    "MergeRequestEventSchema",
    "MergeRequestSchema",
    "NoContentStatusSchema",
    "NotFoundStatusSchema",
    "NoteEventSchema",
    "NoteSchema",
    "NoteableTypeSchema",
    "OkStatusSchema",
    "PipelineAttributesSchema",
    "PipelineEventSchema",
    "PipelineStatusSchema",
    "QueueItemSchema",
    "QueueStateSchema",
    "SecretValueSchema",
    "ServiceUnavailableStatusSchema",
    "UnauthorizedStatusSchema",
    "UnprocessableEntityStatusSchema",
    "WebhookSecretSchema",
    "enum_schema",
]
