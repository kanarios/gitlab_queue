"""Queue Position Notifier for GitLab Merge Queue Bot.

Service for notifying MR authors about queue position changes.
Handles notifications when MRs are added, removed, or positions shift.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.core.notifier import MRNotifier
    from gitlab_queue.core.queue import QueueManager

log = get_logger(__name__)


@dataclass
class QueuePositionNotifier:
    """Service for notifying MR authors about queue position changes.

    Provides methods for:
    - Sending initial position notification when MR is added to queue
    - Notifying affected MRs after an MR is completed (merged/failed/removed)
    - Notifying MRs that moved down after a hotfix was added

    Attributes:
        notifier: MRNotifier for sending comments.
        queue_manager: QueueManager for queue operations.
    """

    notifier: MRNotifier
    queue_manager: QueueManager

    async def notify_initial_position(self, mr_iid: int) -> None:
        """Send initial position notification when MR is added to queue.

        Args:
            mr_iid: Internal ID of the MR that was just added.
        """
        position = await self.queue_manager.get_queue_position(mr_iid)
        total = await self.queue_manager.get_queue_length()

        if position is None:
            log.warning(
                "Cannot notify initial position: MR not in queue",
                mr_iid=mr_iid,
            )
            return

        log.info(
            "Sending initial position notification",
            mr_iid=mr_iid,
            position=position,
            total=total,
        )

        await self.notifier.notify(
            mr_iid,
            "queued",
            position=position,
            total=total,
            estimated_minutes=position * 15,
            queued_at=datetime.now(UTC),
        )

    async def capture_queue_positions(self) -> dict[int, int]:
        """Capture current positions of all queued MRs for comparison.

        Returns:
            Dict mapping mr_iid to 1-indexed position.
        """
        queue_items = await self.queue_manager.get_active_queue()
        positions: dict[int, int] = {}
        for i, item in enumerate(queue_items, start=1):
            positions[item.mr_iid] = i
        return positions

    async def notify_affected_mrs_after_completion(
        self,
        completed_mr_iid: int,
        positions_before: dict[int, int],
    ) -> None:
        """Notify all MRs whose positions changed after an MR completed.

        Only notifies MRs in 'queued' state (not actively processing).

        Args:
            completed_mr_iid: IID of the MR that was just completed.
            positions_before: Positions captured before completion.
        """
        queue_items = await self.queue_manager.get_active_queue()
        total = len(queue_items)

        notified_count = 0
        for item in queue_items:
            # Skip MRs in active processing (not waiting in queue)
            if item.state != "queued":
                continue

            # Skip the completed MR itself (shouldn't be in queue, but just in case)
            if item.mr_iid == completed_mr_iid:
                continue

            old_position = positions_before.get(item.mr_iid)
            if old_position is None:
                continue  # MR was added after capture

            new_position = await self.queue_manager.get_queue_position(item.mr_iid)
            if new_position is None or new_position == old_position:
                continue  # Position unchanged

            log.info(
                "Notifying position change",
                mr_iid=item.mr_iid,
                old_position=old_position,
                new_position=new_position,
            )

            await self.notifier.notify(
                item.mr_iid,
                "position_changed",
                position=new_position,
                total=total,
                old_position=old_position,
                estimated_minutes=new_position * 15,
            )
            notified_count += 1

        if notified_count > 0:
            log.info(
                "Position change notifications sent",
                count=notified_count,
                completed_mr_iid=completed_mr_iid,
            )

    async def notify_affected_mrs_after_hotfix_added(
        self,
        hotfix_mr_iid: int,
        positions_before: dict[int, int],
    ) -> None:
        """Notify MRs that moved down after a hotfix was added.

        When a hotfix is added, it jumps to the front of the queue,
        pushing all other MRs back by one position.

        Args:
            hotfix_mr_iid: IID of the hotfix MR that was just added.
            positions_before: Positions captured before hotfix was added.
        """
        queue_items = await self.queue_manager.get_active_queue()
        total = len(queue_items)

        notified_count = 0
        for item in queue_items:
            # Skip the hotfix MR itself
            if item.mr_iid == hotfix_mr_iid:
                continue

            # Skip MRs in active processing
            if item.state != "queued":
                continue

            old_position = positions_before.get(item.mr_iid)
            if old_position is None:
                continue

            new_position = await self.queue_manager.get_queue_position(item.mr_iid)
            if new_position is None or new_position == old_position:
                continue

            log.info(
                "Notifying position change due to hotfix",
                mr_iid=item.mr_iid,
                old_position=old_position,
                new_position=new_position,
                hotfix_mr_iid=hotfix_mr_iid,
            )

            await self.notifier.notify(
                item.mr_iid,
                "position_changed",
                position=new_position,
                total=total,
                old_position=old_position,
                estimated_minutes=new_position * 15,
            )
            notified_count += 1

        if notified_count > 0:
            log.info(
                "Position change notifications sent after hotfix",
                count=notified_count,
                hotfix_mr_iid=hotfix_mr_iid,
            )


__all__: list[str] = [
    "QueuePositionNotifier",
]
