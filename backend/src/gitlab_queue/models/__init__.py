"""Data models for GitLab Merge Queue Bot.

This module provides dataclass models for representing GitLab entities
and Retort configurations for serialization.
"""

from gitlab_queue.models.events import (
    LabelChanges,
    MergeRequestAttributes,
    MergeRequestEvent,
    NoteEvent,
    PipelineAttributes,
    PipelineEvent,
    validate_webhook_token,
)
from gitlab_queue.models.mr import Author, MergeRequest, Note
from gitlab_queue.models.pipeline import Job, Pipeline
from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.models.retorts import (
    dump_queue_item,
    gitlab_retort,
    load_queue_item,
    parse_job,
    parse_merge_request,
    parse_merge_request_event,
    parse_note,
    parse_note_event,
    parse_pipeline,
    parse_pipeline_event,
    parse_webhook_event,
    sqlite_retort,
)
from gitlab_queue.models.retry import DLQItem, DLQStats, RetryQueueItem

__all__: list[str] = [
    "Author",
    "DLQItem",
    "DLQStats",
    "Job",
    "LabelChanges",
    "MergeRequest",
    "MergeRequestAttributes",
    "MergeRequestEvent",
    "Note",
    "NoteEvent",
    "Pipeline",
    "PipelineAttributes",
    "PipelineEvent",
    "QueueItem",
    "RetryQueueItem",
    "dump_queue_item",
    "gitlab_retort",
    "load_queue_item",
    "parse_job",
    "parse_merge_request",
    "parse_merge_request_event",
    "parse_note",
    "parse_note_event",
    "parse_pipeline",
    "parse_pipeline_event",
    "parse_webhook_event",
    "sqlite_retort",
    "validate_webhook_token",
]
