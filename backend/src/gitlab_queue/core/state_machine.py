"""State Machine for GitLab Merge Queue Bot.

Manages MR lifecycle from queued to merged/failed/removed.
Per ADR-006, each state transition MUST trigger a notification.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from statemachine import State, StateMachine

from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.api.websocket import WebSocketManager
    from gitlab_queue.core.notifier import MRNotifier
    from gitlab_queue.core.queue import QueueManager
    from gitlab_queue.models.queue_item import QueueItem

log = get_logger(__name__)


# =============================================================================
# State Machine
# =============================================================================


class MRStateMachine(StateMachine):
    """State machine for merge request processing.

    Manages MR lifecycle from queued to merged/failed/removed.
    Each state transition triggers:
    1. State persistence to QueueManager
    2. Notification via MRNotifier (mandatory per ADR-006)

    States:
        queued: MR waiting in queue
        rebasing: MR being rebased onto target branch
        testing: Pipeline running after rebase
        merging: MR merge in progress
        merged: Successfully merged (final)
        failed: Processing failed (final)
        removed: Removed from queue (final)

    State Diagram:
        queued → rebasing → testing → merging → merged
                      ↓           ↓
                   failed      failed

        Any state → removed (user removes label or MR closed)

    Example:
        >>> notifier = MRNotifier(gitlab_client, settings)
        >>> queue_manager = QueueManager(db)
        >>> sm = MRStateMachine(notifier, queue_manager, mr_iid=42)
        >>> await sm.trigger_start_processing(target_branch="master")
        >>> await sm.trigger_rebase_complete(pipeline_id=123, pipeline_url="...")
    """

    # =========================================================================
    # States
    # =========================================================================

    queued = State(initial=True)
    rebasing = State()
    testing = State()
    merging = State()
    merged = State(final=True)
    failed = State(final=True)
    removed = State(final=True)

    # =========================================================================
    # Transitions (events)
    # =========================================================================

    start_processing = queued.to(rebasing)
    rebase_complete = rebasing.to(testing)
    rebase_failed = rebasing.to(failed)
    pipeline_success = testing.to(merging)
    pipeline_failed = testing.to(failed)
    merge_success = merging.to(merged)
    merge_failed = merging.to(failed)

    # Any non-final state can transition to removed
    mark_removed = (
        queued.to(removed) | rebasing.to(removed) | testing.to(removed) | merging.to(removed)
    )

    # =========================================================================
    # Constructor
    # =========================================================================

    def __init__(
        self,
        notifier: MRNotifier,
        queue_manager: QueueManager,
        mr_iid: int,
        *,
        target_branch: str = "master",
        start_value: str | None = None,
        websocket_manager: WebSocketManager | None = None,
    ) -> None:
        """Initialize state machine for a specific MR.

        Args:
            notifier: MRNotifier for sending notifications.
            queue_manager: QueueManager for state persistence.
            mr_iid: Merge request IID to manage.
            target_branch: Target branch for rebasing/merging.
            start_value: Initial state (for resuming from DB). If None, starts at queued.
            websocket_manager: Optional WebSocketManager for real-time updates.
        """
        self.notifier = notifier
        self.queue_manager = queue_manager
        self.mr_iid = mr_iid
        self.target_branch = target_branch
        self.websocket_manager: WebSocketManager | None = websocket_manager
        self._context: dict[str, Any] = {}

        # Initialize with correct starting state
        # Note: If start_value matches the initial state, we pass None to avoid
        # triggering the on_enter callback twice
        super().__init__(start_value=start_value if start_value != "queued" else None)

        log.debug(
            "State machine initialized",
            mr_iid=mr_iid,
            initial_state=start_value or "queued",
        )

    # =========================================================================
    # Async Callbacks (MANDATORY per ADR-006)
    # =========================================================================

    async def on_enter_queued(self) -> None:
        """Called when MR enters queued state."""
        log.debug("Entering queued state", mr_iid=self.mr_iid)

        position = await self.queue_manager.get_queue_position(self.mr_iid)
        total = await self.queue_manager.get_queue_length()

        await self.notifier.notify(
            self.mr_iid,
            "queued",
            position=position or 1,
            total=total,
            estimated_minutes=(position or 1) * 15,
            queued_at=datetime.now(UTC),
        )

        # Broadcast WebSocket update
        if self.websocket_manager:
            await self.websocket_manager.broadcast_mr_status_changed(self.mr_iid, "new", "queued")

    async def on_enter_rebasing(self) -> None:
        """Called when MR starts rebasing."""
        log.debug("Entering rebasing state", mr_iid=self.mr_iid)

        await self.queue_manager.update_mr_state(self.mr_iid, "rebasing")
        await self.notifier.notify(
            self.mr_iid,
            "rebasing",
            started_at=datetime.now(UTC),
            target_branch=self.target_branch,
        )

        # Broadcast WebSocket update
        if self.websocket_manager:
            await self.websocket_manager.broadcast_mr_status_changed(
                self.mr_iid, "queued", "rebasing"
            )

    async def on_enter_testing(self) -> None:
        """Called when pipeline starts after rebase."""
        log.debug("Entering testing state", mr_iid=self.mr_iid)

        pipeline_id = self._context.get("pipeline_id")
        pipeline_url = self._context.get("pipeline_url")

        await self.queue_manager.update_mr_state(
            self.mr_iid,
            "testing",
            pipeline_id=pipeline_id,
            pipeline_status="running",
        )
        await self.notifier.notify(
            self.mr_iid,
            "testing",
            pipeline_id=pipeline_id,
            pipeline_url=pipeline_url,
            started_at=datetime.now(UTC),
        )

        # Broadcast WebSocket update
        if self.websocket_manager:
            await self.websocket_manager.broadcast_mr_status_changed(
                self.mr_iid, "rebasing", "testing"
            )

    async def on_enter_merging(self) -> None:
        """Called when pipeline passes and merge starts."""
        log.debug("Entering merging state", mr_iid=self.mr_iid)

        await self.queue_manager.update_mr_state(self.mr_iid, "merging")
        await self.notifier.notify(
            self.mr_iid,
            "merging",
            pipeline_id=self._context.get("pipeline_id"),
            pipeline_url=self._context.get("pipeline_url"),
            target_branch=self.target_branch,
        )

        # Broadcast WebSocket update
        if self.websocket_manager:
            await self.websocket_manager.broadcast_mr_status_changed(
                self.mr_iid, "testing", "merging"
            )

    async def on_enter_merged(self) -> None:
        """Called when MR is successfully merged."""
        log.debug("Entering merged state", mr_iid=self.mr_iid)

        queue_item = await self.queue_manager.get_queue_item(self.mr_iid)
        duration = self._calculate_duration(queue_item)

        await self.queue_manager.update_mr_state(self.mr_iid, "merged")
        await self.notifier.notify(
            self.mr_iid,
            "merged",
            merged_at=datetime.now(UTC),
            duration=duration,
            target_branch=self.target_branch,
        )

        # Broadcast WebSocket completion
        if self.websocket_manager:
            await self.websocket_manager.broadcast_mr_completed(
                self.mr_iid,
                "merged",
                finished_at=datetime.now(UTC),
            )

    async def on_enter_failed(self) -> None:
        """Called when MR fails (conflict, pipeline, timeout)."""
        log.debug("Entering failed state", mr_iid=self.mr_iid)

        failure_reason = self._context.get("failure_reason", "unknown")
        error_message = self._context.get("error_message")

        await self.queue_manager.update_mr_state(
            self.mr_iid,
            "failed",
            last_error=error_message,
        )

        # Choose template based on failure reason
        if failure_reason == "conflict":
            await self.notifier.notify(
                self.mr_iid,
                "conflict",
                failed_at=datetime.now(UTC),
                target_branch=self.target_branch,
                conflicted_files=self._context.get("conflicted_files", []),
            )
        elif failure_reason == "pipeline_failed":
            await self.notifier.notify(
                self.mr_iid,
                "pipeline_failed",
                pipeline_id=self._context.get("pipeline_id"),
                pipeline_url=self._context.get("pipeline_url"),
                failed_at=datetime.now(UTC),
                retry_count=self._context.get("retry_count", 0),
                failed_jobs=self._context.get("failed_jobs", []),
            )
        elif failure_reason == "timeout":
            queue_item = await self.queue_manager.get_queue_item(self.mr_iid)
            await self.notifier.notify(
                self.mr_iid,
                "timeout",
                failed_at=datetime.now(UTC),
                duration=self._calculate_duration(queue_item),
                max_wait=self._context.get("max_wait_hours", 2),
            )
        else:
            # Generic failure - use pipeline_failed template
            await self.notifier.notify(
                self.mr_iid,
                "pipeline_failed",
                pipeline_id=self._context.get("pipeline_id", 0),
                pipeline_url=self._context.get("pipeline_url", "#"),
                failed_at=datetime.now(UTC),
                retry_count=0,
                failed_jobs=[error_message] if error_message else [],
            )

        # Broadcast WebSocket completion
        if self.websocket_manager:
            await self.websocket_manager.broadcast_mr_completed(
                self.mr_iid,
                "failed",
                finished_at=datetime.now(UTC),
                failure_reason=error_message,
            )

    async def on_enter_removed(self) -> None:
        """Called when MR is removed from queue."""
        log.debug("Entering removed state", mr_iid=self.mr_iid)

        removal_reason = self._context.get("removal_reason", "label_removed")
        position = await self.queue_manager.get_queue_position(self.mr_iid)

        await self.queue_manager.update_mr_state(self.mr_iid, "removed")

        if removal_reason == "closed":
            await self.notifier.notify(
                self.mr_iid,
                "removed_closed",
                removed_at=datetime.now(UTC),
            )
        else:
            await self.notifier.notify(
                self.mr_iid,
                "removed_label",
                removed_at=datetime.now(UTC),
                position=position or 0,
            )

        # Broadcast WebSocket completion
        if self.websocket_manager:
            await self.websocket_manager.broadcast_mr_completed(
                self.mr_iid,
                "removed",
                finished_at=datetime.now(UTC),
            )

    # =========================================================================
    # Trigger Methods (context passing)
    # =========================================================================

    async def trigger_start_processing(self) -> None:
        """Start processing the MR (trigger rebase)."""
        log.info("Triggering start_processing", mr_iid=self.mr_iid)
        self._context = {"target_branch": self.target_branch}
        await self.start_processing()

    async def trigger_rebase_complete(
        self,
        *,
        pipeline_id: int,
        pipeline_url: str,
    ) -> None:
        """Rebase completed, pipeline started.

        Args:
            pipeline_id: ID of the new pipeline.
            pipeline_url: URL to the pipeline page.
        """
        log.info(
            "Triggering rebase_complete",
            mr_iid=self.mr_iid,
            pipeline_id=pipeline_id,
        )
        self._context["pipeline_id"] = pipeline_id
        self._context["pipeline_url"] = pipeline_url
        await self.rebase_complete()

    async def trigger_rebase_failed(
        self,
        *,
        conflicted_files: list[str],
        error_message: str,
    ) -> None:
        """Rebase failed due to conflicts.

        Args:
            conflicted_files: List of files with conflicts.
            error_message: Error message for logging.
        """
        log.info(
            "Triggering rebase_failed",
            mr_iid=self.mr_iid,
            conflicted_files=conflicted_files,
        )
        self._context["failure_reason"] = "conflict"
        self._context["conflicted_files"] = conflicted_files
        self._context["error_message"] = error_message
        await self.rebase_failed()

    async def trigger_pipeline_success(self) -> None:
        """Pipeline passed, proceed to merge."""
        log.info("Triggering pipeline_success", mr_iid=self.mr_iid)
        await self.pipeline_success()

    async def trigger_pipeline_failed(
        self,
        *,
        failed_jobs: list[str],
        retry_count: int,
        error_message: str,
    ) -> None:
        """Pipeline failed after retries exhausted.

        Args:
            failed_jobs: List of failed job names.
            retry_count: Number of retry attempts made.
            error_message: Error message for logging.
        """
        log.info(
            "Triggering pipeline_failed",
            mr_iid=self.mr_iid,
            failed_jobs=failed_jobs,
            retry_count=retry_count,
        )
        self._context["failure_reason"] = "pipeline_failed"
        self._context["failed_jobs"] = failed_jobs
        self._context["retry_count"] = retry_count
        self._context["error_message"] = error_message
        await self.pipeline_failed()

    async def trigger_merge_success(self) -> None:
        """MR merged successfully."""
        log.info("Triggering merge_success", mr_iid=self.mr_iid)
        await self.merge_success()

    async def trigger_merge_failed(self, *, error_message: str) -> None:
        """Merge operation failed.

        Args:
            error_message: Error message describing the failure.
        """
        log.info("Triggering merge_failed", mr_iid=self.mr_iid, error=error_message)
        self._context["failure_reason"] = "merge_failed"
        self._context["error_message"] = error_message
        await self.merge_failed()

    async def trigger_mark_removed(self, *, reason: str = "label_removed") -> None:
        """Remove MR from queue.

        Args:
            reason: Reason for removal - "label_removed" or "closed".
        """
        log.info("Triggering mark_removed", mr_iid=self.mr_iid, reason=reason)
        self._context["removal_reason"] = reason
        await self.mark_removed()

    async def trigger_timeout(self, *, max_wait_hours: int = 2) -> None:
        """MR timed out.

        Args:
            max_wait_hours: Maximum wait time that was exceeded.
        """
        log.info("Triggering timeout", mr_iid=self.mr_iid, max_wait_hours=max_wait_hours)
        self._context["failure_reason"] = "timeout"
        self._context["max_wait_hours"] = max_wait_hours
        # Use pipeline_failed transition to go to failed state
        await self.pipeline_failed()

    # =========================================================================
    # Special Notification Methods (no state change)
    # =========================================================================

    async def notify_pipeline_retry(
        self,
        *,
        old_pipeline_id: int,
        old_pipeline_url: str,
        new_pipeline_id: int,
        new_pipeline_url: str,
        retry_count: int,
        max_retries: int,
        failed_jobs: list[str],
    ) -> None:
        """Notify about pipeline retry (stays in testing state).

        Args:
            old_pipeline_id: ID of the failed pipeline.
            old_pipeline_url: URL to the failed pipeline.
            new_pipeline_id: ID of the new retry pipeline.
            new_pipeline_url: URL to the new pipeline.
            retry_count: Current retry attempt number.
            max_retries: Maximum retry attempts configured.
            failed_jobs: List of jobs that failed.
        """
        log.info(
            "Notifying pipeline retry",
            mr_iid=self.mr_iid,
            retry_count=retry_count,
            max_retries=max_retries,
        )

        # Update context for future reference
        self._context["pipeline_id"] = new_pipeline_id
        self._context["pipeline_url"] = new_pipeline_url

        await self.queue_manager.update_mr_state(
            self.mr_iid,
            "testing",
            pipeline_id=new_pipeline_id,
            pipeline_status="running",
            retry_count=retry_count,
        )
        await self.notifier.notify(
            self.mr_iid,
            "pipeline_retry",
            retry_count=retry_count,
            max_retries=max_retries,
            old_pipeline_id=old_pipeline_id,
            old_pipeline_url=old_pipeline_url,
            pipeline_id=new_pipeline_id,
            pipeline_url=new_pipeline_url,
            failed_jobs=failed_jobs,
        )

    async def notify_position_changed(self, *, old_position: int) -> None:
        """Notify about queue position change (stays in queued state).

        Only sends notification if position actually changed.

        Args:
            old_position: Previous position in queue.
        """
        position = await self.queue_manager.get_queue_position(self.mr_iid)
        total = await self.queue_manager.get_queue_length()

        if position and position != old_position:
            log.info(
                "Notifying position changed",
                mr_iid=self.mr_iid,
                old_position=old_position,
                new_position=position,
            )
            await self.notifier.notify(
                self.mr_iid,
                "position_changed",
                position=position,
                total=total,
                old_position=old_position,
                estimated_minutes=position * 15,
            )

    async def notify_rebase_complete(self) -> None:
        """Notify that rebase is complete (before pipeline starts).

        This is an optional intermediate notification between rebasing
        and testing states.
        """
        log.info("Notifying rebase complete", mr_iid=self.mr_iid)
        await self.notifier.notify(
            self.mr_iid,
            "rebase_complete",
            rebased_at=datetime.now(UTC),
        )

    async def notify_stale_warning(self, *, warning_hours: int) -> None:
        """Notify about MR being in queue for extended time (stays in current state).

        This is a warning notification - the MR remains in queue.
        Only sent once per MR (tracked via stale_warning_sent field).

        Args:
            warning_hours: Number of hours threshold that was exceeded.
        """
        log.info(
            "Notifying stale MR warning",
            mr_iid=self.mr_iid,
            warning_hours=warning_hours,
        )

        queue_item = await self.queue_manager.get_queue_item(self.mr_iid)
        position = await self.queue_manager.get_queue_position(self.mr_iid)

        await self.notifier.notify(
            self.mr_iid,
            "stale_warning",
            queued_at=queue_item.queued_at if queue_item else datetime.now(UTC),
            duration=self._calculate_duration(queue_item),
            warning_hours=warning_hours,
            position=position or 1,
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _calculate_duration(self, queue_item: QueueItem | None) -> str:
        """Calculate human-readable duration from queued_at to now.

        Args:
            queue_item: QueueItem with queued_at timestamp.

        Returns:
            Formatted duration string like "1h 23m" or "45s".
        """
        if not queue_item or not queue_item.queued_at:
            return "unknown"

        now = datetime.now(UTC)
        queued_at = queue_item.queued_at

        # Ensure both are timezone-aware
        if queued_at.tzinfo is None:
            queued_at = queued_at.replace(tzinfo=UTC)

        delta = now - queued_at
        total_seconds = int(delta.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"


# =============================================================================
# Factory Function
# =============================================================================


async def create_state_machine_for_mr(
    mr_iid: int,
    notifier: MRNotifier,
    queue_manager: QueueManager,
    *,
    target_branch: str = "master",
    websocket_manager: WebSocketManager | None = None,
) -> MRStateMachine:
    """Create state machine for an MR, resuming from DB state if exists.

    Args:
        mr_iid: Merge request IID.
        notifier: MRNotifier for sending notifications.
        queue_manager: QueueManager for state persistence.
        target_branch: Target branch for rebasing/merging.
        websocket_manager: Optional WebSocketManager for real-time updates.

    Returns:
        MRStateMachine initialized with the correct state.
    """
    queue_item = await queue_manager.get_queue_item(mr_iid)

    if queue_item:
        log.debug(
            "Creating state machine from existing queue item",
            mr_iid=mr_iid,
            existing_state=queue_item.state,
        )
        sm = MRStateMachine(
            notifier=notifier,
            queue_manager=queue_manager,
            mr_iid=mr_iid,
            target_branch=target_branch,
            start_value=queue_item.state,
            websocket_manager=websocket_manager,
        )
    else:
        log.debug("Creating new state machine", mr_iid=mr_iid)
        sm = MRStateMachine(
            notifier=notifier,
            queue_manager=queue_manager,
            mr_iid=mr_iid,
            target_branch=target_branch,
            websocket_manager=websocket_manager,
        )

    await sm.activate_initial_state()  # type: ignore[no-untyped-call]
    return sm


__all__: list[str] = [
    "MRStateMachine",
    "create_state_machine_for_mr",
]
