from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from gitlab_queue.models.queue_item import QueueItem

if TYPE_CHECKING:
    from gitlab_queue.models.mr import MergeRequest


@dataclass
class FakeQueueManager:
    _items: dict[int, QueueItem] = field(default_factory=dict)
    _completed: dict[int, dict[str, Any]] = field(default_factory=dict)

    # Sequential responses (overrides normal behavior when non-empty)
    get_queue_item_sequence: list[QueueItem | None] = field(default_factory=list)
    get_next_mr_sequence: list[QueueItem | Exception | None] = field(default_factory=list)

    # Configurable responses for dashboard
    dashboard_stats: Any = None
    recent_history: list[QueueItem] = field(default_factory=list)
    queue_stats: dict[str, int] | None = None

    # Error injection
    update_state_error: Exception | None = None
    add_error: Exception | None = None
    get_active_queue_error: Exception | None = None

    # Cross-fake call order tracking
    call_order_log: list[str] | None = None

    # Call recording
    complete_calls: list[dict[str, Any]] = field(default_factory=list)
    remove_calls: list[int] = field(default_factory=list)
    stale_warning_calls: list[int] = field(default_factory=list)
    update_state_calls: list[dict[str, Any]] = field(default_factory=list)
    add_to_queue_calls: list[dict[str, Any]] = field(default_factory=list)
    update_hotfix_calls: list[dict[str, Any]] = field(default_factory=list)
    get_queue_item_calls: list[int] = field(default_factory=list)

    def add_item(self, item: QueueItem) -> None:
        self._items[item.mr_iid] = item

    async def add_to_queue(self, project_id: int, mr: MergeRequest, is_hotfix: bool = False) -> QueueItem:
        self.add_to_queue_calls.append({"project_id": project_id, "mr": mr, "is_hotfix": is_hotfix})
        if self.add_error:
            raise self.add_error
        item = QueueItem(
            mr_iid=mr.iid,
            title=mr.title,
            author_name=mr.author.name,
            author_username=mr.author.username,
            target_branch=mr.target_branch,
            state="queued",
            queued_at=datetime.now(UTC),
            project_id=project_id,
            is_hotfix=is_hotfix,
            labels=mr.labels,
        )
        self._items[mr.iid] = item
        return item

    async def remove_from_queue(self, project_id: int, mr_iid: int) -> bool:
        self.remove_calls.append(mr_iid)
        return self._items.pop(mr_iid, None) is not None

    async def get_queue_position(self, project_id: int, mr_iid: int) -> int | None:
        items = sorted(self._items.values(), key=lambda i: i.queued_at)
        for pos, item in enumerate(items, start=1):
            if item.mr_iid == mr_iid:
                return pos
        return None

    async def get_next_mr(self, project_id: int) -> QueueItem | None:
        if self.get_next_mr_sequence:
            item = self.get_next_mr_sequence.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        queued = [i for i in self._items.values() if i.state == "queued"]
        if not queued:
            return None
        return min(queued, key=lambda i: (not i.is_hotfix, i.queued_at))

    async def get_queue_item(self, project_id: int, mr_iid: int) -> QueueItem | None:
        self.get_queue_item_calls.append(mr_iid)
        if self.get_queue_item_sequence:
            return self.get_queue_item_sequence.pop(0)
        return self._items.get(mr_iid)

    async def get_active_queue(self, project_id: int | None = None) -> list[QueueItem]:
        if self.get_active_queue_error:
            raise self.get_active_queue_error
        return sorted(self._items.values(), key=lambda i: i.queued_at)

    async def get_queue_length(self, project_id: int | None = None) -> int:
        return len(self._items)

    async def get_mr_state(self, project_id: int, mr_iid: int) -> dict[str, Any] | None:
        item = self._items.get(mr_iid)
        if item is None:
            return None
        return {"state": item.state}

    async def update_mr_state(self, project_id: int, mr_iid: int, state: str, **extra: Any) -> bool:
        self.update_state_calls.append({"mr_iid": mr_iid, "state": state, **extra})
        if self.update_state_error:
            raise self.update_state_error
        item = self._items.get(mr_iid)
        if item is None:
            return False
        item.state = state
        for key, value in extra.items():
            if hasattr(item, key):
                setattr(item, key, value)
        return True

    async def update_hotfix_status(self, project_id: int, mr_iid: int, is_hotfix: bool, labels: list[str]) -> bool:
        self.update_hotfix_calls.append(
            {
                "mr_iid": mr_iid,
                "is_hotfix": is_hotfix,
                "labels": labels,
            }
        )
        item = self._items.get(mr_iid)
        if item is None:
            return False
        item.is_hotfix = is_hotfix
        item.labels = labels
        return True

    async def complete_mr(
        self,
        project_id: int,
        mr_iid: int,
        status: str,
        failure_reason: str | None = None,
        pipeline_duration_seconds: int | None = None,
        pipeline_failed_jobs: list[str] | None = None,
    ) -> bool:
        self.complete_calls.append(
            {
                "mr_iid": mr_iid,
                "status": status,
                "failure_reason": failure_reason,
                "pipeline_duration_seconds": pipeline_duration_seconds,
                "pipeline_failed_jobs": pipeline_failed_jobs,
            }
        )
        if self.call_order_log is not None:
            self.call_order_log.append("complete_mr")
        item = self._items.get(mr_iid)
        if item is None:
            return False
        item.state = status
        item.finished_at = datetime.now(UTC)
        return True

    async def get_queue_stats(self, project_id: int | None = None) -> dict[str, int]:
        if self.queue_stats is not None:
            return self.queue_stats
        return {"queued": len(self._items)}

    async def get_stale_mrs(self, project_id: int, hours: int) -> list[QueueItem]:
        return [i for i in self._items.values() if i.stale_warning_sent is False]

    async def mark_stale_warning_sent(self, project_id: int, mr_iid: int) -> bool:
        self.stale_warning_calls.append(mr_iid)
        item = self._items.get(mr_iid)
        if item is None:
            return False
        item.stale_warning_sent = True
        return True

    async def get_recent_history(self, limit: int = 10, project_id: int | None = None) -> list[QueueItem]:
        return self.recent_history[:limit]

    async def get_dashboard_stats(self, days: int = 7, project_id: int | None = None) -> Any:
        if self.dashboard_stats is not None:
            return self.dashboard_stats
        from gitlab_queue.models.queue_item import DashboardStats

        return DashboardStats(
            total_in_queue=len(self._items),
            stats_window_days=days,
            merged_count=0,
            failed_count=0,
            success_rate=0.0,
            avg_wait_seconds=0,
            avg_processing_seconds=0,
        )
