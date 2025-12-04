"""Webhook event models for GitLab Merge Queue Bot.

Provides immutable dataclass representations of GitLab webhook payloads.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class MergeRequestAttributes:
    """Merge request attributes from webhook payload.

    Attributes:
        iid: Internal ID (project-scoped MR number)
        title: MR title
        state: Current state (opened, merged, closed)
        action: Event action (open, close, reopen, update, merge, approved, etc.)
        source_branch: Branch being merged from
        target_branch: Branch being merged into
        merge_status: Merge readiness status
        sha: Current HEAD commit SHA
        has_conflicts: Whether MR has merge conflicts
        rebase_in_progress: Whether rebase is currently running
        web_url: URL to the MR in GitLab UI
    """

    iid: int
    title: str
    state: str
    action: str
    source_branch: str
    target_branch: str
    merge_status: str
    sha: str | None = None
    has_conflicts: bool = False
    rebase_in_progress: bool = False
    web_url: str | None = None


@dataclass(frozen=True, slots=True)
class PipelineAttributes:
    """Pipeline attributes from webhook payload.

    Attributes:
        id: Pipeline ID
        status: Pipeline status (pending, running, success, failed, canceled)
        sha: Commit SHA for the pipeline
        ref: Git ref (branch/tag) for the pipeline
        web_url: URL to the pipeline in GitLab UI
        created_at: When the pipeline was created
    """

    id: int
    status: str
    sha: str
    ref: str
    web_url: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class LabelChanges:
    """Label changes from webhook payload.

    Tracks which labels were added/removed during a merge request update.

    Attributes:
        previous: Labels before the change
        current: Labels after the change
    """

    previous: list[str] = field(default_factory=list)
    current: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class MergeRequestEvent:
    """GitLab merge_request webhook event.

    Represents the full payload from a merge request webhook.

    Attributes:
        object_kind: Event type identifier ("merge_request")
        event_type: Event type ("merge_request")
        project_id: GitLab project ID
        object_attributes: MR attributes
        user_id: ID of the user who triggered the event
        user_name: Name of the user
        user_username: Username of the user
        user_avatar: Avatar URL of the user
        labels: Current labels on the MR
        label_changes: Label changes if this is a label update event
    """

    object_kind: str
    event_type: str
    project_id: int
    object_attributes: MergeRequestAttributes
    user_id: int
    user_name: str
    user_username: str
    user_avatar: str | None = None
    labels: list[str] = field(default_factory=list)
    label_changes: LabelChanges | None = None


@dataclass(frozen=True, slots=True)
class PipelineEvent:
    """GitLab pipeline webhook event.

    Represents the full payload from a pipeline webhook.

    Attributes:
        object_kind: Event type identifier ("pipeline")
        project_id: GitLab project ID
        object_attributes: Pipeline attributes
        merge_request_iid: MR IID if pipeline is for a merge request
    """

    object_kind: str
    project_id: int
    object_attributes: PipelineAttributes
    merge_request_iid: int | None = None


@dataclass(frozen=True, slots=True)
class NoteEvent:
    """GitLab note webhook event.

    Represents the full payload from a note (comment) webhook.

    Attributes:
        object_kind: Event type identifier ("note")
        event_type: Event type ("note")
        project_id: GitLab project ID
        user_id: ID of the user who created the note
        user_name: Name of the user
        user_username: Username of the user
        note_id: Note ID
        note_body: Note content (supports markdown)
        noteable_type: Type of object the note is on ("MergeRequest", "Issue", etc.)
        merge_request_iid: MR IID if note is on a merge request
    """

    object_kind: str
    event_type: str
    project_id: int
    user_id: int
    user_name: str
    user_username: str
    note_id: int
    note_body: str
    noteable_type: str
    merge_request_iid: int | None = None


def validate_webhook_token(token: str, secret: str) -> bool:
    """Validate GitLab webhook token using constant-time comparison.

    GitLab sends the secret token in X-Gitlab-Token header.
    Uses constant-time comparison to prevent timing attacks.

    Args:
        token: Token from X-Gitlab-Token header
        secret: Expected secret value

    Returns:
        True if token matches secret, False otherwise
    """
    return hmac.compare_digest(token, secret)


__all__: list[str] = [
    "LabelChanges",
    "MergeRequestAttributes",
    "MergeRequestEvent",
    "NoteEvent",
    "PipelineAttributes",
    "PipelineEvent",
    "validate_webhook_token",
]
