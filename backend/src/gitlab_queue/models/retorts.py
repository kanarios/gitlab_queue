"""Adaptix Retort configurations for data serialization.

Provides Retort instances for converting between:
- GitLab API JSON responses → dataclass models
- Dataclass models → SQLite storage format
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from adaptix import P, Retort, name_mapping

from gitlab_queue.models.events import (
    LabelChanges,
    MergeRequestAttributes,
    MergeRequestEvent,
    NoteEvent,
    PipelineAttributes,
    PipelineEvent,
)
from gitlab_queue.models.mr import Author, MergeRequest, Note
from gitlab_queue.models.pipeline import Job, Pipeline
from gitlab_queue.models.queue_item import QueueItem


def _extract_labels(labels: list[Any]) -> list[str]:
    """Extract label names from GitLab API response or webhook payload.

    GitLab can return labels in different formats:
    - List of strings: ["label1", "label2"]
    - List of objects from API: [{"name": "label1"}, {"name": "label2"}]
    - List of objects from webhooks: [{"title": "label1"}, {"title": "label2"}]

    Args:
        labels: Labels from API response or webhook payload

    Returns:
        List of label name strings
    """
    if not labels:
        return []

    extracted: list[str] = []
    for label in labels:
        if label is None:
            continue

        value: str | None = None
        if isinstance(label, dict):
            raw = label.get("name") or label.get("title")
            if raw is not None:
                value = str(raw)
        elif isinstance(label, str):
            value = label
        else:
            # Unknown label format: ignore instead of raising.
            continue

        if value is None:
            continue
        value = value.strip()
        if not value:
            continue
        extracted.append(value)

    return extracted


# Retort for parsing GitLab API responses into dataclass models
gitlab_retort = Retort(
    recipe=[
        # Map GitLab API field names to our dataclass field names
        name_mapping(
            P[MergeRequest],
            map={
                "has_conflicts": ("has_conflicts", "detailed_merge_status"),
            },
            extra_in="skip",  # Skip unknown fields from API
        ),
        name_mapping(
            P[Author],
            extra_in="skip",  # Skip unknown fields from API
        ),
    ]
)


def parse_merge_request(data: dict[str, Any]) -> MergeRequest:
    """Parse GitLab API response into MergeRequest model.

    Handles the complexity of GitLab API response format including
    nested author object and label extraction.

    Args:
        data: Raw JSON response from GitLab API

    Returns:
        MergeRequest instance
    """
    # Extract and normalize data for our model
    author_data = data.get("author", {})
    author = Author(
        id=author_data.get("id", 0),
        name=author_data.get("name", ""),
        username=author_data.get("username", ""),
        avatar_url=author_data.get("avatar_url"),
    )

    # Determine has_conflicts from multiple possible fields
    has_conflicts = data.get("has_conflicts", False)
    if not has_conflicts:
        # Check detailed_merge_status for conflict indicators
        detailed_status = data.get("detailed_merge_status", "")
        has_conflicts = detailed_status in ("conflict", "has_conflicts")

    return MergeRequest(
        iid=data["iid"],
        title=data["title"],
        state=data["state"],
        labels=_extract_labels(data.get("labels", [])),
        sha=data.get("sha", ""),
        source_branch=data["source_branch"],
        target_branch=data["target_branch"],
        merge_status=data.get("merge_status", ""),
        author=author,
        has_conflicts=has_conflicts,
        rebase_in_progress=data.get("rebase_in_progress", False),
        web_url=data.get("web_url"),
        merge_error=data.get("merge_error"),
        detailed_merge_status=data.get("detailed_merge_status"),
    )


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO datetime string from GitLab API.

    GitLab returns timestamps in ISO 8601 format with Z suffix.

    Args:
        value: ISO datetime string or None

    Returns:
        datetime object or None
    """
    if not value:
        return None
    # Handle "YYYY-MM-DD HH:MM:SS UTC" format from GitLab pipeline webhooks
    if value.endswith(" UTC"):
        return datetime.fromisoformat(value[:-4] + "+00:00")
    # Handle Z suffix (UTC timezone)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_pipeline(data: dict[str, Any]) -> Pipeline:
    """Parse GitLab API response into Pipeline model.

    Args:
        data: Raw JSON response from GitLab API

    Returns:
        Pipeline instance
    """
    return Pipeline(
        id=data["id"],
        status=data["status"],
        sha=data.get("sha", ""),
        ref=data.get("ref", ""),
        web_url=data.get("web_url"),
        created_at=_parse_datetime(data.get("created_at")),
    )


def parse_job(data: dict[str, Any]) -> Job:
    """Parse GitLab API response into Job model.

    Args:
        data: Raw JSON response from GitLab API

    Returns:
        Job instance
    """
    return Job(
        id=data["id"],
        name=data["name"],
        status=data["status"],
        stage=data.get("stage", ""),
        web_url=data.get("web_url"),
    )


def parse_note(data: dict[str, Any]) -> Note:
    """Parse GitLab API response into Note model.

    Args:
        data: Raw JSON response from GitLab API

    Returns:
        Note instance
    """
    author_data = data.get("author", {})
    author = Author(
        id=author_data.get("id", 0),
        name=author_data.get("name", ""),
        username=author_data.get("username", ""),
        avatar_url=author_data.get("avatar_url"),
    )
    return Note(
        id=data["id"],
        body=data.get("body", ""),
        author=author,
        system=data.get("system", False),
    )


# Retort for SQLite JSON storage serialization
# Used for serializing/deserializing QueueItem and other models to/from SQLite
sqlite_retort = Retort(
    recipe=[
        # No special recipe needed - adaptix handles datetime serialization
        # by default using ISO format strings
        name_mapping(
            P[QueueItem],
            extra_in="skip",  # Skip unknown fields when loading
        ),
    ]
)


def dump_queue_item(item: QueueItem) -> dict[str, Any]:
    """Serialize QueueItem to dict for SQLite JSON storage.

    Args:
        item: QueueItem instance to serialize

    Returns:
        Dictionary with ISO datetime strings
    """
    return {
        "mr_iid": item.mr_iid,
        "title": item.title,
        "author_name": item.author_name,
        "author_username": item.author_username,
        "author_avatar": item.author_avatar,
        "target_branch": item.target_branch,
        "state": item.state,
        "is_hotfix": item.is_hotfix,
        "labels": item.labels,
        "queued_at": item.queued_at.isoformat(),
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "pipeline_id": item.pipeline_id,
        "pipeline_status": item.pipeline_status,
        "retry_count": item.get_max_job_retry_count(),
        "retried_jobs": item.retried_jobs,
        "last_error": item.last_error,
        "expected_sha": item.expected_sha,
    }


def load_queue_item(data: dict[str, Any]) -> QueueItem:
    """Deserialize dict from SQLite JSON storage to QueueItem.

    Args:
        data: Dictionary from SQLite storage

    Returns:
        QueueItem instance
    """
    queued_at = data["queued_at"]
    if isinstance(queued_at, str):
        queued_at = datetime.fromisoformat(queued_at)

    started_at = data.get("started_at")
    if isinstance(started_at, str):
        started_at = datetime.fromisoformat(started_at)

    # Handle labels - could be JSON string or already a list
    labels = data.get("labels", [])
    if isinstance(labels, str):
        import json

        labels = json.loads(labels) if labels else []

    return QueueItem(
        mr_iid=data["mr_iid"],
        title=data["title"],
        author_name=data["author_name"],
        author_username=data["author_username"],
        target_branch=data["target_branch"],
        state=data["state"],
        queued_at=queued_at,
        is_hotfix=bool(data.get("is_hotfix", False)),
        author_avatar=data.get("author_avatar"),
        labels=labels,
        started_at=started_at,
        pipeline_id=data.get("pipeline_id"),
        pipeline_status=data.get("pipeline_status"),
        retry_count=data.get("retry_count", 0),
        retried_jobs=data.get("retried_jobs", {}),
        last_error=data.get("last_error"),
        expected_sha=data.get("expected_sha"),
    )


# ===== Webhook Event Parsing =====


def parse_merge_request_event(data: dict[str, Any]) -> MergeRequestEvent:
    """Parse GitLab merge_request webhook payload.

    Args:
        data: Raw JSON webhook payload

    Returns:
        MergeRequestEvent instance
    """
    attrs = data["object_attributes"]
    user = data.get("user", {})

    # Extract label changes if present
    label_changes = None
    if "changes" in data and "labels" in data["changes"]:
        changes = data["changes"]["labels"]
        label_changes = LabelChanges(
            previous=_extract_labels(changes.get("previous", [])),
            current=_extract_labels(changes.get("current", [])),
        )

    # Get SHA from last_commit if available
    last_commit = attrs.get("last_commit")
    sha = last_commit.get("id") if last_commit else None

    return MergeRequestEvent(
        object_kind=data["object_kind"],
        event_type=data.get("event_type", "merge_request"),
        project_id=data["project"]["id"],
        object_attributes=MergeRequestAttributes(
            iid=attrs["iid"],
            title=attrs["title"],
            state=attrs["state"],
            action=attrs.get("action", ""),
            source_branch=attrs["source_branch"],
            target_branch=attrs["target_branch"],
            merge_status=attrs.get("merge_status", ""),
            sha=sha,
            has_conflicts=attrs.get("has_conflicts", False),
            rebase_in_progress=attrs.get("rebase_in_progress", False),
            web_url=attrs.get("url"),
        ),
        user_id=user.get("id", 0),
        user_name=user.get("name", ""),
        user_username=user.get("username", ""),
        user_avatar=user.get("avatar_url"),
        labels=_extract_labels(data.get("labels", [])),
        label_changes=label_changes,
    )


def parse_pipeline_event(data: dict[str, Any]) -> PipelineEvent:
    """Parse GitLab pipeline webhook payload.

    Args:
        data: Raw JSON webhook payload

    Returns:
        PipelineEvent instance
    """
    attrs = data["object_attributes"]
    mr = data.get("merge_request")

    return PipelineEvent(
        object_kind=data["object_kind"],
        project_id=data["project"]["id"],
        object_attributes=PipelineAttributes(
            id=attrs["id"],
            status=attrs["status"],
            sha=attrs.get("sha", ""),
            ref=attrs.get("ref", ""),
            web_url=attrs.get("url"),
            created_at=_parse_datetime(attrs.get("created_at")),
        ),
        merge_request_iid=mr.get("iid") if mr else None,
    )


def parse_note_event(data: dict[str, Any]) -> NoteEvent:
    """Parse GitLab note webhook payload.

    Args:
        data: Raw JSON webhook payload

    Returns:
        NoteEvent instance
    """
    attrs = data["object_attributes"]
    user = data.get("user", {})
    mr = data.get("merge_request")

    return NoteEvent(
        object_kind=data["object_kind"],
        event_type=data.get("event_type", "note"),
        project_id=data["project"]["id"],
        user_id=user.get("id", 0),
        user_name=user.get("name", ""),
        user_username=user.get("username", ""),
        note_id=attrs["id"],
        note_body=attrs.get("note", ""),
        noteable_type=attrs.get("noteable_type", ""),
        merge_request_iid=mr.get("iid") if mr else None,
    )


def parse_webhook_event(
    data: dict[str, Any],
) -> MergeRequestEvent | PipelineEvent | NoteEvent | None:
    """Route webhook payload to appropriate parser based on object_kind.

    Args:
        data: Raw JSON webhook payload

    Returns:
        Parsed event instance, or None for unknown event types
        (caller should handle logging for unknown events)
    """
    object_kind = data.get("object_kind")
    if object_kind == "merge_request":
        return parse_merge_request_event(data)
    elif object_kind == "pipeline":
        return parse_pipeline_event(data)
    elif object_kind == "note":
        return parse_note_event(data)
    return None


__all__: list[str] = [
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
]
