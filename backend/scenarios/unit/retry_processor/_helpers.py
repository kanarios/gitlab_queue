"""Helpers for retry processor test scenarios."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from gitlab_queue.models.retry import RetryQueueItem
from gitlab_queue.webhooks.retry_processor import WebhookRetryProcessor


def create_mock_retry_manager() -> MagicMock:
    """Create a mock WebhookRetryManager with default return values."""
    rm = MagicMock()
    rm.get_events_ready_for_retry = AsyncMock(return_value=[])
    rm.mark_retry_success = AsyncMock()
    rm.mark_retry_failed = AsyncMock(return_value=False)
    rm.ensure_schema = AsyncMock()
    return rm


def create_mock_settings() -> MagicMock:
    """Create a mock Settings with default values."""
    s = MagicMock()
    s.webhook_retry_poll_interval_seconds = 1
    s.queue_label = "merge_queue"
    s.hotfix_label = "hotfix"
    s.target_branch = "main"
    s.gitlab_project_id = 1
    return s


def create_test_retry_processor(**overrides: Any) -> WebhookRetryProcessor:
    """Create a WebhookRetryProcessor with mock dependencies.

    Args:
        **overrides: Keyword arguments to override default mock dependencies.

    Returns:
        Configured WebhookRetryProcessor instance.
    """
    defaults: dict[str, Any] = {
        "retry_manager": create_mock_retry_manager(),
        "settings": create_mock_settings(),
        "gitlab_client": MagicMock(),
        "queue_manager": MagicMock(),
        "notifier": MagicMock(),
    }
    defaults.update(overrides)
    return WebhookRetryProcessor(**defaults)


def create_mr_payload() -> dict[str, Any]:
    """Create a valid merge_request webhook payload."""
    return {
        "object_kind": "merge_request",
        "event_type": "merge_request",
        "project": {"id": 1},
        "object_attributes": {
            "iid": 42,
            "action": "update",
            "state": "opened",
            "target_branch": "main",
            "source_branch": "feature",
            "title": "Test MR",
            "merge_status": "can_be_merged",
        },
        "user": {"id": 1, "name": "Test", "username": "test"},
        "labels": [{"title": "merge_queue"}],
    }


def create_pipeline_payload() -> dict[str, Any]:
    """Create a valid pipeline webhook payload."""
    return {
        "object_kind": "pipeline",
        "project": {"id": 1},
        "object_attributes": {
            "id": 100,
            "status": "success",
            "sha": "abc123",
            "ref": "feature",
        },
        "merge_request": {"iid": 42},
    }


def create_test_retry_item(
    id: int = 1,
    event_type: str = "merge_request",
    payload: dict[str, Any] | None = None,
    attempt_count: int = 0,
) -> RetryQueueItem:
    """Create a RetryQueueItem for testing.

    Args:
        id: Item ID.
        event_type: Event type string.
        payload: Webhook payload dict (auto-generated if None).
        attempt_count: Number of attempts already made.

    Returns:
        RetryQueueItem instance.
    """
    if payload is None:
        if event_type == "merge_request":
            payload = create_mr_payload()
        else:
            payload = create_pipeline_payload()

    return RetryQueueItem(
        id=id,
        event_type=event_type,
        payload=payload,
        attempt_count=attempt_count,
        max_attempts=3,
        next_attempt_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )


__all__ = [
    "create_mock_retry_manager",
    "create_mock_settings",
    "create_mr_payload",
    "create_pipeline_payload",
    "create_test_retry_item",
    "create_test_retry_processor",
]
