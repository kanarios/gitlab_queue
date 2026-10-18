"""Reconcile labels without restarting an MR's processing workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from gitlab_queue.models.priority import effective_priority

if TYPE_CHECKING:
    from gitlab_queue.core.protocols import QueueManagerProtocol
    from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier


@dataclass
class QueueMetadataUpdater:
    queue_manager: QueueManagerProtocol
    hotfix_label: str
    position_notifier: QueuePositionNotifier | None = None

    async def refresh(
        self,
        project_id: int,
        mr_iid: int,
        labels: list[str],
        *,
        expected_revision: tuple[int, int] | None = None,
        notify: bool = True,
        admission_key: str | None = None,
    ) -> bool:
        async with self.queue_manager.metadata_lock(project_id):
            updated = await self._refresh(project_id, mr_iid, labels, expected_revision, admission_key)
            if notify:
                await self.retry_pending(project_id)
            return updated

    async def retry_pending(self, project_id: int) -> None:
        if self.position_notifier:
            await self.position_notifier.retry_pending(project_id)

    async def _refresh(
        self,
        project_id: int,
        mr_iid: int,
        labels: list[str],
        expected_revision: tuple[int, int] | None,
        admission_key: str | None = None,
    ) -> bool:
        item = await self.queue_manager.get_queue_item(project_id, mr_iid)
        if item is None or item.state not in ("queued", "rebasing", "testing", "merging"):
            return False

        revision = (item.queue_id, item.metadata_version)
        if expected_revision is not None and expected_revision != revision:
            return False

        is_hotfix, is_automated = self.queue_manager.classify_labels(project_id, labels, self.hotfix_label in labels)
        priority_changed = effective_priority(item.is_hotfix, item.is_automated) != effective_priority(
            is_hotfix, is_automated
        )
        if not priority_changed and set(item.labels) == set(labels) and admission_key is None:
            return False

        updated = await self.queue_manager.update_hotfix_status(
            project_id,
            mr_iid,
            is_hotfix,
            labels,
            expected_revision=revision,
            notify_positions=priority_changed,
            admission_key=admission_key,
            is_automated=is_automated,
        )
        return updated
