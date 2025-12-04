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
    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.core.queue import QueueManager

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

    async def run(self) -> None:
        """Main polling loop - runs until shutdown signal.

        Polls GitLab at regular intervals (poll_interval_seconds)
        to synchronize the queue state.
        """
        log.info(
            "Queue scheduler starting",
            poll_interval_seconds=self.settings.poll_interval_seconds,
        )

        try:
            while not self._shutdown_event.is_set():
                try:
                    stats = await self.sync_queue()
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

        # Find MRs to add (in GitLab but not in queue)
        mrs_to_add = gitlab_mr_iids - queue_mr_iids
        if mrs_to_add:
            log.info(
                "Found MRs with label not in queue",
                count=len(mrs_to_add),
                mr_iids=list(mrs_to_add),
            )
            for mr in gitlab_mrs:
                if mr.iid in mrs_to_add:
                    await self._add_mr_to_queue(mr)
                    stats.added += 1

        # Find MRs to check for removal (in queue but not in GitLab list)
        mrs_to_check = queue_mr_iids - gitlab_mr_iids
        if mrs_to_check:
            log.info(
                "Found queue entries not in GitLab label list",
                count=len(mrs_to_check),
                mr_iids=list(mrs_to_check),
            )
            for item in queue_items:
                if item.mr_iid in mrs_to_check:
                    should_remove = await self._should_remove_from_queue(item.mr_iid)
                    if should_remove:
                        await self.queue_manager.remove_from_queue(item.mr_iid)
                        stats.removed += 1
                        log.info(
                            "Removed orphaned MR from queue",
                            mr_iid=item.mr_iid,
                        )

        # Count unchanged
        stats.unchanged = len(gitlab_mr_iids & queue_mr_iids)

        return stats

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
