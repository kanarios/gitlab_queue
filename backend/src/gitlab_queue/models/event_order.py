"""Source timestamps are intervals, not receipt-order revisions.

Nonoverlapping intervals establish order. With overlapping intervals an enqueue
wins over a cancellation; two enqueue requests preserve their combined triggers.
This deliberately preserves intent when GitLab's timestamp precision cannot
establish order. Message identity still makes redelivery idempotent.
"""

from datetime import datetime, timedelta
from typing import Any


def definitely_before(event_at: datetime, precision_us: int, boundary: datetime) -> bool:
    return event_at + timedelta(microseconds=precision_us) <= boundary


def compare_event(request: dict[str, Any], previous: dict[str, Any]) -> int:
    """Return -1/1 for proved order, 0 for overlapping or missing intervals."""
    incoming, saved = request.get("requested_at"), previous.get("requested_at")
    if incoming is None or saved is None:
        return 0
    start, old = datetime.fromisoformat(incoming), datetime.fromisoformat(saved)
    if definitely_before(start, request.get("precision_us", 1), old):
        return -1
    if definitely_before(old, previous.get("precision_us", 1), start):
        return 1
    return 0


def preserve_uncertainty(request: dict[str, Any], previous: dict[str, Any]) -> None:
    """Merging overlapping enqueues cannot make either source clock more precise."""
    incoming, saved = request.get("requested_at"), previous.get("requested_at")
    if incoming is None or saved is None:
        request["requested_at"] = None
        return
    start, old = datetime.fromisoformat(incoming), datetime.fromisoformat(saved)
    lower = min(start, old)
    upper = max(
        start + timedelta(microseconds=request.get("precision_us", 1)),
        old + timedelta(microseconds=previous.get("precision_us", 1)),
    )
    request["requested_at"] = lower.isoformat()
    width = upper - lower
    request["precision_us"] = width // timedelta(microseconds=1)
