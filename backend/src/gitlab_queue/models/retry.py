"""Retry queue data models for GitLab Merge Queue Bot.

Provides dataclass representations for webhook retry queue and
Dead Letter Queue (DLQ) items.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class RetryQueueItem:
    """Item in the webhook retry queue.

    Frozen dataclass since items are read from database and not modified
    in-place (updates create new database rows or update existing ones).

    Attributes:
        id: Database primary key
        event_type: Type of webhook event ('merge_request' or 'pipeline')
        payload: Original webhook payload as dict
        attempt_count: Number of retry attempts made so far
        max_attempts: Maximum attempts before moving to DLQ
        next_attempt_at: When the next retry should be attempted
        last_error: Error message from the last failed attempt
        created_at: When the item was first added to the retry queue
    """

    id: int
    event_type: str
    payload: dict[str, Any]
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime
    created_at: datetime
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class DLQItem:
    """Item in the Dead Letter Queue.

    Represents a webhook event that failed all retry attempts
    and has been moved to the DLQ for manual investigation.

    Attributes:
        id: Database primary key
        event_type: Type of webhook event ('merge_request' or 'pipeline')
        payload: Original webhook payload as dict
        attempt_count: Total number of attempts made
        last_error: Error message from the final failed attempt
        original_created_at: When the item was first received
        moved_to_dlq_at: When the item was moved to the DLQ
    """

    id: int
    event_type: str
    payload: dict[str, Any]
    attempt_count: int
    last_error: str
    original_created_at: datetime
    moved_to_dlq_at: datetime


@dataclass(frozen=True, slots=True)
class DLQStats:
    """Statistics about the Dead Letter Queue.

    Attributes:
        total_count: Total number of items in the DLQ
        by_event_type: Count of items grouped by event type
        oldest_entry: Timestamp of the oldest DLQ entry (or None if empty)
    """

    total_count: int
    by_event_type: dict[str, int]
    oldest_entry: datetime | None


__all__: list[str] = [
    "DLQItem",
    "DLQStats",
    "RetryQueueItem",
]
