from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakePositionNotifier:
    """Fake QueuePositionNotifier for testing webhook handlers.

    Records all calls for assertion and supports error injection.
    """

    # Configurable responses
    captured_positions: dict[int, int] = field(default_factory=dict)

    # Error injection
    notify_initial_error: Exception | None = None

    # Call recording
    notify_initial_calls: list[int] = field(default_factory=list)
    capture_calls: list[None] = field(default_factory=list)
    notify_after_completion_calls: list[dict[str, Any]] = field(default_factory=list)
    notify_after_add_calls: list[dict[str, Any]] = field(default_factory=list)

    async def notify_initial_position(self, project_id: int, mr_iid: int) -> None:
        self.notify_initial_calls.append(mr_iid)
        if self.notify_initial_error is not None:
            raise self.notify_initial_error

    async def capture_queue_positions(self, project_id: int) -> dict[int, int]:
        self.capture_calls.append(None)
        return self.captured_positions

    async def notify_affected_mrs_after_completion(
        self,
        project_id: int,
        completed_mr_iid: int,
        positions_before: dict[int, int],
        old_total: int,
    ) -> None:
        self.notify_after_completion_calls.append(
            {
                "completed_mr_iid": completed_mr_iid,
                "positions_before": positions_before,
                "old_total": old_total,
            }
        )

    async def notify_affected_mrs_after_mr_added(
        self,
        project_id: int,
        added_mr_iid: int,
        positions_before: dict[int, int],
        old_total: int,
        *,
        is_hotfix: bool = False,
    ) -> None:
        self.notify_after_add_calls.append(
            {
                "added_mr_iid": added_mr_iid,
                "positions_before": positions_before,
                "old_total": old_total,
                "is_hotfix": is_hotfix,
            }
        )
