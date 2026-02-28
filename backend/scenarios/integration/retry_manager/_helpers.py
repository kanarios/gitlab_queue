from __future__ import annotations

from typing import TYPE_CHECKING

from gitlab_queue.webhooks.retry_manager import WebhookRetryManager

if TYPE_CHECKING:
    from gitlab_queue.db.database import Database


def create_test_retry_manager(db: Database, **kwargs) -> WebhookRetryManager:
    """
    Create a WebhookRetryManager configured for tests with sensible default retry settings.

    Defaults:
    - db: the provided Database instance
    - max_attempts: 3
    - base_delay_seconds: 1
    - max_delay_seconds: 10

    Parameters:
        kwargs: Optional overrides for the default retry settings; accepted keys include
            'max_attempts', 'base_delay_seconds', 'max_delay_seconds', and any other
            keyword arguments accepted by WebhookRetryManager.

    Returns:
        WebhookRetryManager: A new WebhookRetryManager instance configured with the merged settings.
    """
    defaults = {
        "db": db,
        "max_attempts": 3,
        "base_delay_seconds": 1,
        "max_delay_seconds": 10,
    }
    defaults.update(kwargs)
    return WebhookRetryManager(**defaults)


def create_test_payload(event_type: str = "merge_request") -> dict:
    """
    Create a representative webhook payload for tests based on the specified event type.

    Parameters:
        event_type (str): Type of event to generate. If "merge_request" returns a merge request payload; any other value returns a pipeline-like payload.

    Returns:
        dict: A webhook payload dict with keys "object_kind", "project", and "object_attributes".
    """
    if event_type == "merge_request":
        return {
            "object_kind": "merge_request",
            "project": {"id": 1},
            "object_attributes": {"iid": 42, "action": "update"},
        }
    return {
        "object_kind": "pipeline",
        "project": {"id": 1},
        "object_attributes": {"id": 100, "status": "failed"},
    }
