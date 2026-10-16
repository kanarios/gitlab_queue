"""Reconcile labels without restarting an MR's processing workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.core.protocols import QueueManagerProtocol
    from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier

log = get_logger(__name__)


@dataclass
class QueueMetadataUpdater:
    queue_manager: QueueManagerProtocol
    hotfix_label: str
    position_notifier: QueuePositionNotifier | None = None

    async def refresh(self, project_id: int, mr_iid: int, labels: list[str]) -> bool:
        item = await self.queue_manager.get_queue_item(project_id, mr_iid)
        if item is None or item.state not in ("queued", "rebasing", "testing", "merging"):
            return False

        is_hotfix = self.hotfix_label in labels
        priority_changed = item.is_hotfix != is_hotfix
        if not priority_changed and set(item.labels) == set(labels):
            return False

        positions_before: dict[int, int] = {}
        if priority_changed and self.position_notifier:
            positions_before = await self.position_notifier.capture_queue_positions(project_id)

        updated = await self.queue_manager.update_hotfix_status(project_id, mr_iid, is_hotfix, labels)
        if updated and priority_changed and self.position_notifier:
            try:
                await self.position_notifier.notify_priority_changed(project_id, mr_iid, positions_before)
            except Exception as error:
                log.warning("Failed to notify priority change", mr_iid=mr_iid, error=str(error))
        return updated
