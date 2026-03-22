"""Queue Position Notifier for GitLab Merge Queue Bot.

Service for notifying MR authors about queue position changes.
Handles notifications when MRs are added, removed, or positions shift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.core.notifier import MRNotifier
    from gitlab_queue.core.queue import QueueManager

log = get_logger(__name__)

# Estimated processing time per queue position (minutes)
ESTIMATED_MINUTES_PER_POSITION = 15


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

    async def notify_initial_position(self, project_id: int, mr_iid: int) -> None:
        """Send initial position notification when MR is added to queue.

        Args:
            project_id: GitLab project ID.
            mr_iid: Internal ID of the MR that was just added.
        """
        queue_items = await self.queue_manager.get_active_queue(project_id)
        total = len(queue_items)

        position: int | None = None
        matched_item = None
        for i, item in enumerate(queue_items, start=1):
            if item.mr_iid == mr_iid:
                position = i
                matched_item = item
                break

        if position is None or matched_item is None:
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

        # Estimated time includes processing time for all MRs ahead plus this MR
        estimated_minutes = position * ESTIMATED_MINUTES_PER_POSITION
        await self.notifier.notify(
            mr_iid,
            "queued",
            position=position,
            total=total,
            estimated_minutes=estimated_minutes,
            queued_at=matched_item.queued_at,
        )

    async def capture_queue_positions(self, project_id: int) -> dict[int, int]:
        """Capture current positions of queued MRs for comparison.

        Args:
            project_id: GitLab project ID.

        Only captures MRs in 'queued' state (not actively processing).

        Returns:
            Dict mapping mr_iid to 1-indexed position.
        """
        queue_items = await self.queue_manager.get_active_queue(project_id)
        positions: dict[int, int] = {}
        for i, item in enumerate(queue_items, start=1):
            if item.state == "queued":
                positions[item.mr_iid] = i
        return positions

    def _select_notification_template(
        self,
        position_changed: bool,
        is_hotfix: bool,
    ) -> str:
        """Select notification template based on what changed.

        Args:
            position_changed: Whether the position changed.
            is_hotfix: Whether the triggering MR was a hotfix.

        Returns:
            Template name to use for notification.
        """
        if position_changed and is_hotfix:
            return "position_changed_hotfix"
        if position_changed:
            return "position_changed"
        if is_hotfix:
            return "total_changed_hotfix"
        return "total_changed"

    async def _notify_position_changes(
        self,
        project_id: int,
        excluded_mr_iid: int,
        positions_before: dict[int, int],
        old_total: int,
        log_context: str,
        *,
        is_hotfix: bool = False,
    ) -> int:
        """Notify MRs whose positions or total changed, excluding a specific MR.

        Args:
            project_id: GitLab project ID.
            excluded_mr_iid: IID of MR to exclude from notifications.
            positions_before: Positions captured before the change.
            old_total: Total queue size before the change.
            log_context: Context string for log messages (e.g., "due to hotfix").
            is_hotfix: Whether the triggering MR was a hotfix (affects template choice).

        Returns:
            Number of MRs notified.
        """
        queue_items = await self.queue_manager.get_active_queue(project_id)
        total = len(queue_items)

        # Build position map synchronously from queue_items
        position_map: dict[int, int] = {}
        for i, item in enumerate(queue_items, start=1):
            if item.state == "queued":
                position_map[item.mr_iid] = i

        notified_count = 0
        for item in queue_items:
            if item.state != "queued" or item.mr_iid == excluded_mr_iid:
                continue

            old_position = positions_before.get(item.mr_iid)
            new_position = position_map.get(item.mr_iid)
            if old_position is None or new_position is None:
                continue

            position_changed = new_position != old_position
            total_changed = total != old_total
            if not position_changed and not total_changed:
                continue

            template = self._select_notification_template(position_changed, is_hotfix)

            log.info(
                "Notifying position/total change",
                mr_iid=item.mr_iid,
                old_position=old_position,
                new_position=new_position,
                old_total=old_total,
                new_total=total,
                template=template,
                context=log_context.strip() if log_context else None,
            )

            await self.notifier.notify(
                item.mr_iid,
                template,
                position=new_position,
                total=total,
                old_position=old_position,
                old_total=old_total,
                estimated_minutes=new_position * ESTIMATED_MINUTES_PER_POSITION,
            )
            notified_count += 1

        return notified_count

    async def notify_affected_mrs_after_completion(
        self,
        project_id: int,
        completed_mr_iid: int,
        positions_before: dict[int, int],
        old_total: int,
    ) -> None:
        """Notify all MRs whose positions changed after an MR completed.

        Only notifies MRs in 'queued' state (not actively processing).

        Args:
            project_id: GitLab project ID.
            completed_mr_iid: IID of the MR that was just completed.
            positions_before: Positions captured before completion.
            old_total: Total queue size before the completion.
        """
        notified_count = await self._notify_position_changes(
            project_id=project_id,
            excluded_mr_iid=completed_mr_iid,
            positions_before=positions_before,
            old_total=old_total,
            log_context="",
        )

        if notified_count > 0:
            log.info(
                "Position change notifications sent",
                count=notified_count,
                completed_mr_iid=completed_mr_iid,
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
        """Notify MRs whose position or total changed after an MR was added.

        When an MR is added to the queue, existing MRs need to be notified
        about the updated queue size. If it's a hotfix, positions also shift.

        Args:
            project_id: GitLab project ID.
            added_mr_iid: IID of the MR that was just added.
            positions_before: Positions captured before the MR was added.
            old_total: Total queue size before the MR was added.
            is_hotfix: Whether the added MR is a hotfix (for logging context).
        """
        log_context = " due to hotfix" if is_hotfix else ""
        notified_count = await self._notify_position_changes(
            project_id=project_id,
            excluded_mr_iid=added_mr_iid,
            positions_before=positions_before,
            old_total=old_total,
            log_context=log_context,
            is_hotfix=is_hotfix,
        )

        if notified_count > 0:
            log.info(
                "Position/total change notifications sent after MR added",
                count=notified_count,
                added_mr_iid=added_mr_iid,
                is_hotfix=is_hotfix,
            )


__all__: list[str] = [
    "QueuePositionNotifier",
]
