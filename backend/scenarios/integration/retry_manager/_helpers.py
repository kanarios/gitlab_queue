from __future__ import annotations

from gitlab_queue.db.database import Database
from gitlab_queue.webhooks.retry_manager import WebhookRetryManager


def create_test_retry_manager(db: Database, **kwargs) -> WebhookRetryManager:
    defaults = {
        "db": db,
        "max_attempts": 3,
        "base_delay_seconds": 1,
        "max_delay_seconds": 10,
    }
    defaults.update(kwargs)
    return WebhookRetryManager(**defaults)


def create_test_payload(event_type: str = "merge_request") -> dict:
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
