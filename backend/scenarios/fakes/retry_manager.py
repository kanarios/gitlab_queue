from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gitlab_queue.models.retry import RetryQueueItem


@dataclass
class FakeRetryManager:
    _ready_events: list[RetryQueueItem] = field(default_factory=list)
    _dlq_on_fail: bool = False
    get_events_error: Exception | None = None

    # DLQ configurable responses
    dlq_entries: list[Any] = field(default_factory=list)
    dlq_stats: Any = None  # Will be set by test if needed
    dlq_entry: Any = None
    dlq_error: Exception | None = None

    # Delete behavior
    delete_result: bool = True

    # Call recording
    success_calls: list[int] = field(default_factory=list)
    failed_calls: list[dict[str, Any]] = field(default_factory=list)
    ensure_schema_calls: int = field(default=0)

    # Additional call recording
    add_to_retry_queue_calls: list[dict[str, Any]] = field(default_factory=list)
    retry_dlq_calls: list[int] = field(default_factory=list)
    delete_dlq_calls: list[int] = field(default_factory=list)

    # Auto-increment ID for add_to_retry_queue
    _next_id: int = field(default=1)

    async def get_events_ready_for_retry(self, limit: int = 10) -> list[RetryQueueItem]:
        if self.get_events_error:
            raise self.get_events_error
        return self._ready_events[:limit]

    async def mark_retry_success(self, item_id: int) -> None:
        self.success_calls.append(item_id)

    async def mark_retry_failed(self, item_id: int, error_message: str) -> bool:
        self.failed_calls.append({"item_id": item_id, "error_message": error_message})
        return self._dlq_on_fail

    async def ensure_schema(self) -> None:
        self.ensure_schema_calls += 1

    async def add_to_retry_queue(self, event_type: str, payload: dict[str, Any], error: str) -> int:
        self.add_to_retry_queue_calls.append(
            {
                "event_type": event_type,
                "payload": payload,
                "error": error,
            }
        )
        current_id = self._next_id
        self._next_id += 1
        return current_id

    async def get_dlq_entries(self, limit: int = 50, offset: int = 0, event_type: str | None = None) -> list[Any]:
        return self.dlq_entries[offset : offset + limit]

    async def get_dlq_stats(self) -> Any:
        if self.dlq_stats is not None:
            return self.dlq_stats
        # Return a minimal stats-like object
        return type(
            "DLQStats",
            (),
            {
                "total_count": len(self.dlq_entries),
                "by_event_type": {},
                "oldest_entry": None,
            },
        )()

    async def get_dlq_entry(self, entry_id: int) -> Any:
        if self.dlq_error:
            raise self.dlq_error
        if self.dlq_entry is not None:
            return self.dlq_entry
        raise Exception(f"DLQ entry {entry_id} not found")

    async def retry_dlq_entry(self, entry_id: int) -> int:
        self.retry_dlq_calls.append(entry_id)
        if self.dlq_error:
            raise self.dlq_error
        current_id = self._next_id
        self._next_id += 1
        return current_id

    async def delete_dlq_entry(self, entry_id: int) -> bool:
        self.delete_dlq_calls.append(entry_id)
        return self.delete_result
