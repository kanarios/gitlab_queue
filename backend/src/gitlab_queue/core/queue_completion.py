"""Finish an owned lifecycle, and resume it after interruption.

Lock order is completion → notification → short database transaction. No
transaction spans GitLab HTTP. The durable row owns cleanup until archival.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from gitlab_queue.models.completion import requeue_is_cancelled
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.api.websocket import WebSocketManager
    from gitlab_queue.core.protocols import NotifierProtocol, QueueManagerProtocol
    from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier
    from gitlab_queue.models.completion import CompletionRequest
    from gitlab_queue.models.queue_item import QueueItem

log = get_logger(__name__)


@dataclass
class QueueCompletion:
    queue: QueueManagerProtocol
    notifier: NotifierProtocol
    positions: QueuePositionNotifier | None = None
    websocket: WebSocketManager | None = None

    async def complete(self, project_id: int, mr_iid: int, request: CompletionRequest) -> None:
        async with self.queue.completion_lock(project_id, mr_iid):
            async with self.queue.notification_lock(project_id, mr_iid):
                item = await self.queue.prepare_completion(project_id, mr_iid, request)
            if item is not None:
                await self._finish(project_id, item)

    async def recover(self, project_id: int, mr_iid: int, queue_id: int) -> None:
        async with self.queue.completion_lock(project_id, mr_iid):
            item = await self.queue.get_queue_item(project_id, mr_iid)
            if item is not None and item.queue_id == queue_id and item.pending_completion is not None:
                await self._finish(project_id, item)

    async def recover_all(self, project_id: int) -> bool:
        pending = await self.queue.get_pending_completions(project_id)
        for item in pending:
            try:
                await self.recover(project_id, item.mr_iid, item.queue_id)
            except Exception as error:
                log.warning("Completion remains pending", mr_iid=item.mr_iid, error=str(error))
        return bool(pending)

    async def _deliver_comment(self, project_id: int, item: QueueItem, payload: dict[str, Any]) -> None:
        if payload["comment_sent"]:
            return
        request = payload["request"]
        context = dict(request["context"])
        for key, value in context.items():
            if key.endswith("_at") and isinstance(value, str):
                context[key] = datetime.fromisoformat(value)
        await self.notifier.notify(item.mr_iid, request["notification_status"], **context)
        payload["comment_sent"] = True
        await self.queue.save_completion_progress(project_id, item.queue_id, payload)

    async def _record_label_event(
        self, project_id: int, item: QueueItem, payload: dict[str, Any], event_at: datetime | None
    ) -> None:
        if event_at is not None:
            payload["label_events"].append(event_at.isoformat())
        await self.queue.save_completion_progress(project_id, item.queue_id, payload)

    async def _cleanup(self, project_id: int, item: QueueItem, payload: dict[str, Any]) -> None:
        if payload["request"]["remove_labels"] and not payload["labels_removed"]:
            event_at = await self.notifier.remove_queue_label(item.mr_iid, strict=True)
            payload["labels_removed"] = True
            await self._record_label_event(project_id, item, payload, event_at)

    async def _finish(self, project_id: int, item: QueueItem) -> None:
        payload: dict[str, Any] = json.loads(item.pending_completion or "{}")
        await self._deliver_comment(project_id, item, payload)
        await self._cleanup(project_id, item, payload)
        current = await self.queue.get_queue_item(project_id, item.mr_iid)
        if current is None or current.queue_id != item.queue_id:
            return
        if current.requeue_request is not None:
            requeue = json.loads(current.requeue_request)
            if requeue_is_cancelled(requeue, payload["label_events"]):
                event_at = await self.notifier.remove_queue_label(item.mr_iid, strict=True)
            else:
                event_at = await self.notifier.restore_queue_labels(item.mr_iid, requeue["triggers"])
            await self._record_label_event(project_id, item, payload, event_at)
        if await self.queue.finalize_completion(project_id, current, payload):
            await self._after_completion(project_id, item, payload)

    async def _after_completion(self, project_id: int, item: QueueItem, payload: dict[str, Any]) -> None:
        request = payload["request"]
        if self.positions is not None:
            positions = {int(iid): pos for iid, pos in request["positions"].items()}
            await self.positions.notify_affected_mrs_after_completion(
                project_id, item.mr_iid, positions, request["old_total"]
            )
        if self.websocket is not None:
            await self.websocket.broadcast_mr_completed(
                item.mr_iid,
                "merged" if request["history_status"] == "merged" else request["state"],
                finished_at=datetime.fromisoformat(payload["finished_at"]),
                project_id=project_id,
            )
