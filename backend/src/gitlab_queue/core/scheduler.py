"""Polling Fallback Scheduler for GitLab Merge Queue Bot.

Provides periodic polling to discover missed webhook events and synchronize
the queue state with GitLab. This acts as a safety net when webhooks fail
to deliver or are missed.

The scheduler:
1. Periodically polls GitLab for MRs with the queue label
2. Adds missing MRs to the queue (webhook delivery failure recovery)
3. Removes orphaned queue entries (MR closed/merged or label removed)
4. Runs independently of webhooks to ensure queue consistency
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gitlab_queue.clients.gitlab import GitLabAPIError, GitLabNotFoundError
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.api.websocket import WebSocketManager
    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.core.queue import QueueManager
    from gitlab_queue.models.mr import MergeRequest
    from gitlab_queue.models.queue_item import QueueItem

log = get_logger(__name__)


@dataclass
class SyncStats:
    """Statistics from a single sync operation."""

    mrs_in_gitlab: int = 0
    mrs_in_queue: int = 0
    added: int = 0
    removed: int = 0
    unchanged: int = 0


@dataclass
class QueueScheduler:
    """Periodic polling scheduler for queue synchronization.

    Runs in the background, periodically polling GitLab to discover
    MRs that should be in the queue but aren't (missed webhooks) and
    removing MRs that no longer belong (closed/merged/unlabeled).

    Attributes:
        gitlab_client: GitLab API client.
        queue_manager: Queue manager for MR storage.
        settings: Application settings.

    Example:
        >>> scheduler = QueueScheduler(gitlab_client, queue_manager, settings)
        >>> # Start in background
        >>> task = asyncio.create_task(scheduler.run())
        >>> # ... later, to stop
        >>> scheduler.request_shutdown()
        >>> await task
    """

    gitlab_client: GitLabClient
    queue_manager: QueueManager
    settings: Settings

    # Internal state
    _shutdown_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _sync_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _websocket_manager: WebSocketManager | None = field(default=None, init=False)

    def set_websocket_manager(self, manager: WebSocketManager) -> None:
        """Set WebSocket manager for broadcasting queue updates.

        Called after webhook server is initialized to enable real-time updates.

        Args:
            manager: WebSocketManager instance.
        """
        self._websocket_manager = manager
        log.debug("WebSocket manager set for scheduler")

    async def run(self) -> None:
        """Main polling loop - runs until shutdown signal.

        Polls GitLab at regular intervals (poll_interval_seconds)
        to synchronize the queue state. Respects rate limit state and
        pauses polling when at critical limit.
        """
        log.info(
            "Queue scheduler starting",
            poll_interval_seconds=self.settings.poll_interval_seconds,
        )

        try:
            while not self._shutdown_event.is_set():
                # Check rate limit before sync
                should_pause, pause_seconds = self._should_pause_for_rate_limit()
                if should_pause:
                    if not await self._interruptible_sleep(pause_seconds):
                        break
                    continue

                try:
                    stats = await self.sync_queue()

                    # Log queue stats at INFO level for visibility
                    log.info(
                        "Queue stats",
                        queue_depth=stats.mrs_in_queue,
                        mrs_with_label=stats.mrs_in_gitlab,
                        added=stats.added,
                        removed=stats.removed,
                    )

                    log.debug(
                        "Queue sync completed",
                        mrs_in_gitlab=stats.mrs_in_gitlab,
                        mrs_in_queue=stats.mrs_in_queue,
                        added=stats.added,
                        removed=stats.removed,
                        unchanged=stats.unchanged,
                    )
                except GitLabAPIError as e:
                    log.warning(
                        "Queue sync failed due to GitLab API error",
                        error=str(e),
                    )
                except Exception as e:
                    log.exception("Queue sync failed", error=str(e))

                # Wait for next poll interval
                if not await self._interruptible_sleep(self.settings.poll_interval_seconds):
                    break
        finally:
            log.info("Queue scheduler stopped")

    def _should_pause_for_rate_limit(self) -> tuple[bool, float]:
        """Check if polling should pause due to rate limit pressure.

        Pauses polling when GitLab API rate limit is at critical level
        to prevent further API calls and allow the limit to reset.

        Returns:
            Tuple of (should_pause, pause_seconds).
            If should_pause is True, caller should wait pause_seconds
            before making any API calls.
        """
        state = self.gitlab_client.rate_limit_state
        critical_threshold = self.settings.rate_limit_critical_threshold

        if state.is_critical(critical_threshold):
            # At critical limit, wait until reset
            pause = state.seconds_until_reset or 60.0
            log.warning(
                "Pausing scheduler due to critical rate limit",
                pause_seconds=round(pause, 1),
                usage_ratio=state.usage_ratio,
                reset_seconds=state.seconds_until_reset,
            )
            return True, pause

        return False, 0.0

    async def sync_queue(self) -> SyncStats:
        """Synchronize queue state with GitLab.

        Performs a full sync by:
        1. Listing all MRs with queue label from GitLab
        2. Comparing with current queue state
        3. Adding missing MRs (discovered from GitLab but not in queue)
        4. Removing orphaned entries (in queue but no longer valid in GitLab)

        Returns:
            SyncStats with counts of changes made.
        """
        async with self._sync_lock:
            return await self._do_sync()

    async def _do_sync(self) -> SyncStats:
        """Internal sync implementation.

        Must be called while holding _sync_lock.
        """
        stats = SyncStats()

        # Get current state from GitLab
        log.debug("Fetching MRs with queue label from GitLab")
        gitlab_mrs = await self.gitlab_client.list_mrs_with_label(
            self.settings.queue_label,
            state="opened",
        )
        stats.mrs_in_gitlab = len(gitlab_mrs)

        # Build set of MR IIDs from GitLab
        gitlab_mr_iids = {mr.iid for mr in gitlab_mrs}

        # Get current queue state from database
        queue_items = await self.queue_manager.get_active_queue()
        stats.mrs_in_queue = len(queue_items)

        # Build set of MR IIDs from queue
        queue_mr_iids = {item.mr_iid for item in queue_items}

        # Sync: add missing MRs, remove orphaned MRs
        stats.added = await self._add_missing_mrs(gitlab_mrs, queue_mr_iids)
        stats.removed = await self._remove_orphaned_mrs(queue_items, gitlab_mr_iids)
        stats.unchanged = len(gitlab_mr_iids & queue_mr_iids)

        # Broadcast and update stats if queue changed
        if stats.added > 0 or stats.removed > 0:
            await self._finalize_sync(stats)

        return stats

    async def _add_missing_mrs(self, gitlab_mrs: list[MergeRequest], queue_mr_iids: set[int]) -> int:
        """Add MRs that are in GitLab but not in queue.

        Args:
            gitlab_mrs: List of MRs from GitLab (sorted by created_at ASC for FIFO).
            queue_mr_iids: Set of MR IIDs currently in queue.

        Returns:
            Number of MRs added.
        """
        mrs_to_add = [mr for mr in gitlab_mrs if mr.iid not in queue_mr_iids]
        if not mrs_to_add:
            return 0

        log.info(
            "Found MRs with label not in queue",
            count=len(mrs_to_add),
            mr_iids=[mr.iid for mr in mrs_to_add],
        )
        for mr in mrs_to_add:
            await self._add_mr_to_queue(mr)

        return len(mrs_to_add)

    async def _remove_orphaned_mrs(self, queue_items: list[QueueItem], gitlab_mr_iids: set[int]) -> int:
        """Remove MRs that are in queue but no longer in GitLab.

        Args:
            queue_items: List of items currently in queue.
            gitlab_mr_iids: Set of MR IIDs from GitLab.

        Returns:
            Number of MRs removed.
        """
        queue_mr_iids = {item.mr_iid for item in queue_items}
        mrs_to_check = queue_mr_iids - gitlab_mr_iids
        if not mrs_to_check:
            return 0

        log.info(
            "Found queue entries not in GitLab label list",
            count=len(mrs_to_check),
            mr_iids=list(mrs_to_check),
        )

        removed_count = 0
        for item in queue_items:
            if item.mr_iid not in mrs_to_check:
                continue
            if await self._should_remove_from_queue(item.mr_iid):
                await self.queue_manager.remove_from_queue(item.mr_iid)
                removed_count += 1
                log.info("Removed orphaned MR from queue", mr_iid=item.mr_iid)

        return removed_count

    async def _finalize_sync(self, stats: SyncStats) -> None:
        """Broadcast updates and refresh queue stats after sync changes.

        Args:
            stats: SyncStats to update with final queue depth.
        """
        if self._websocket_manager:
            await self._broadcast_queue_update()

        updated_queue = await self.queue_manager.get_active_queue()
        stats.mrs_in_queue = len(updated_queue)

    async def _broadcast_queue_update(self) -> None:
        """Broadcast current queue state to all WebSocket clients."""
        if not self._websocket_manager:
            return

        try:
            queue_items = await self.queue_manager.get_active_queue()
            queue_stats = await self.queue_manager.get_queue_stats()

            # Convert queue items to dicts for WebSocket
            queue_data = []
            for i, item in enumerate(queue_items, start=1):
                queue_data.append(
                    {
                        "mr_iid": item.mr_iid,
                        "title": item.title,
                        "author": {
                            "name": item.author_name,
                            "username": item.author_username,
                            "avatar_url": item.author_avatar,
                        },
                        "target_branch": item.target_branch,
                        "status": item.state,
                        "is_hotfix": item.is_hotfix,
                        "labels": item.labels,
                        "queued_at": item.queued_at.isoformat(),
                        "started_at": item.started_at.isoformat() if item.started_at else None,
                        "position": i,
                    }
                )

            await self._websocket_manager.broadcast_queue_updated(queue_data, queue_stats)
            log.debug(
                "Broadcast queue update to WebSocket clients",
                queue_length=len(queue_data),
            )
        except Exception as e:
            log.warning("Failed to broadcast queue update", error=str(e))

    async def _add_mr_to_queue(self, mr: object) -> None:
        """Add a discovered MR to the queue.

        Args:
            mr: MergeRequest object from GitLab API.
        """
        from gitlab_queue.models.mr import MergeRequest

        if not isinstance(mr, MergeRequest):
            return

        # Check if hotfix label is present
        is_hotfix = self.settings.hotfix_label in mr.labels

        await self.queue_manager.add_to_queue(mr, is_hotfix=is_hotfix)
        log.info(
            "Added MR to queue via polling fallback",
            mr_iid=mr.iid,
            title=mr.title,
            is_hotfix=is_hotfix,
        )

    async def _should_remove_from_queue(self, mr_iid: int) -> bool:
        """Check if an MR should be removed from queue.

        An MR should be removed if:
        - It no longer exists in GitLab (404)
        - It is closed or merged
        - It no longer has the queue label

        Args:
            mr_iid: MR IID to check.

        Returns:
            True if MR should be removed from queue.
        """
        try:
            mr = await self.gitlab_client.get_mr(mr_iid)

            # MR closed or merged - remove
            if mr.state != "opened":
                log.debug(
                    "MR no longer open, marking for removal",
                    mr_iid=mr_iid,
                    state=mr.state,
                )
                return True

            # Queue label removed - remove
            if self.settings.queue_label not in mr.labels:
                log.debug(
                    "MR no longer has queue label, marking for removal",
                    mr_iid=mr_iid,
                )
                return True

            # MR is still valid - do not remove
            # This can happen if GitLab API pagination missed it
            log.debug(
                "MR still valid, keeping in queue",
                mr_iid=mr_iid,
            )
            return False

        except GitLabNotFoundError:
            log.warning(
                "MR not found in GitLab, marking for removal",
                mr_iid=mr_iid,
            )
            return True

    async def _interruptible_sleep(self, seconds: float) -> bool:
        """Sleep that can be interrupted by shutdown event.

        Args:
            seconds: Number of seconds to sleep.

        Returns:
            True if sleep completed, False if interrupted by shutdown.
        """
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=seconds,
            )
            return False
        except TimeoutError:
            return True

    def request_shutdown(self) -> None:
        """Request graceful shutdown of the scheduler."""
        log.info("Scheduler shutdown requested")
        self._shutdown_event.set()

    @property
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_event.is_set()


def create_scheduler(
    gitlab_client: GitLabClient,
    queue_manager: QueueManager,
    settings: Settings,
) -> QueueScheduler:
    """Create a configured QueueScheduler instance.

    Args:
        gitlab_client: GitLab API client.
        queue_manager: Queue manager for MR storage.
        settings: Application settings.

    Returns:
        Configured QueueScheduler ready to run.
    """
    return QueueScheduler(
        gitlab_client=gitlab_client,
        queue_manager=queue_manager,
        settings=settings,
    )


__all__: list[str] = [
    "QueueScheduler",
    "SyncStats",
    "create_scheduler",
]
