"""Helpers for retry processor test scenarios."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from gitlab_queue.models.retry import RetryQueueItem
from gitlab_queue.webhooks.retry_processor import WebhookRetryProcessor
from scenarios.fakes import (
    FakeGitLabClient,
    FakeHandlerFactory,
    FakeNotifier,
    FakeQueueManager,
    FakeRetryManager,
    FakeSettings,
)


def create_fake_retry_manager(**overrides: Any) -> FakeRetryManager:
    """Create a FakeRetryManager with optional overrides."""
    return FakeRetryManager(**overrides)


def create_test_settings(**overrides: Any) -> FakeSettings:
    """Create a FakeSettings with default values for retry processor tests."""
    return FakeSettings(**overrides)


def create_test_retry_processor(**overrides: Any) -> WebhookRetryProcessor:
    """Create a WebhookRetryProcessor with fake dependencies.

    Args:
        **overrides: Keyword arguments to override default dependencies.

    Returns:
        Configured WebhookRetryProcessor instance.
    """
    defaults: dict[str, Any] = {
        "retry_manager": create_fake_retry_manager(),
        "settings": create_test_settings(),
        "gitlab_client": FakeGitLabClient(),
        "queue_manager": FakeQueueManager(),
        "notifier": FakeNotifier(),
        "mr_handler_factory": FakeHandlerFactory(),
        "pipeline_handler_factory": FakeHandlerFactory(),
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
    item_id: int = 1,
    event_type: str = "merge_request",
    payload: dict[str, Any] | None = None,
    attempt_count: int = 0,
) -> RetryQueueItem:
    """Create a RetryQueueItem for testing."""
    if payload is None:
        payload = create_mr_payload() if event_type == "merge_request" else create_pipeline_payload()

    return RetryQueueItem(
        id=item_id,
        event_type=event_type,
        payload=payload,
        attempt_count=attempt_count,
        max_attempts=3,
        next_attempt_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )


__all__ = [
    "create_fake_retry_manager",
    "create_mr_payload",
    "create_pipeline_payload",
    "create_test_retry_item",
    "create_test_retry_processor",
    "create_test_settings",
]
