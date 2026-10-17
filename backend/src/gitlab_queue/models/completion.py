"""The immutable outcome of one queue lifecycle."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CompletionRequest:
    state: str
    history_status: str
    notification_status: str
    context: dict[str, Any]
    failure_reason: str | None = None
    pipeline_duration_seconds: int | None = None
    pipeline_failed_jobs: list[str] | None = None
    remove_labels: bool = True
    positions: dict[int, int] = field(default_factory=dict)
    old_total: int = 0
    queue_id: int | None = None


def requeue_is_cancelled(request: dict[str, Any], own_events: list[str]) -> bool:
    """Bot cleanup events cannot cancel a user's explicit enqueue request."""
    return any(event not in own_events for event in request.get("cancelled_events", []))
