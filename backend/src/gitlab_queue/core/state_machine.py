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
    from gitlab_queue.core.protocols import NotifierProtocol, QueueManagerProtocol, StateMachineProtocol
    from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier
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

    # Error recovery: any non-final intermediate state can reset to queued
    reset_to_queued = rebasing.to(queued) | testing.to(queued) | merging.to(queued)

    # Any non-final state can transition to removed
    mark_removed = queued.to(removed) | rebasing.to(removed) | testing.to(removed) | merging.to(removed)

    # =========================================================================
    # Constructor
    # =========================================================================

    def __init__(
        self,
        notifier: NotifierProtocol,
        queue_manager: QueueManagerProtocol,
        mr_iid: int,
        *,
        target_branch: str = "master",
        start_value: str | None = None,
        websocket_manager: WebSocketManager | None = None,
        position_notifier: QueuePositionNotifier | None = None,
        skip_initial_enter: bool = False,
    ) -> None:
        """Initialize state machine for a specific MR.

        Args:
            notifier: Notifier for sending notifications.
            queue_manager: Queue manager for state persistence.
            mr_iid: Merge request IID to manage.
            target_branch: Target branch for rebasing/merging.
            start_value: Initial state (for resuming from DB). If None, starts at queued.
            websocket_manager: Optional WebSocketManager for real-time updates.
            position_notifier: Optional QueuePositionNotifier for position change notifications.
        """
        self.notifier = notifier
        self.queue_manager = queue_manager
        self.mr_iid = mr_iid
        self.target_branch = target_branch
        self.websocket_manager: WebSocketManager | None = websocket_manager
        self.position_notifier: QueuePositionNotifier | None = position_notifier
        self._context: dict[str, Any] = {}
        self._skip_initial_enter = skip_initial_enter

        # Initialize with correct starting state
        # Note: If start_value matches the initial state, we pass None to avoid
        # triggering the on_enter callback twice
        super().__init__(start_value=start_value if start_value != "queued" else None)

        log.debug(
            "State machine initialized",
            mr_iid=mr_iid,
            initial_state=start_value or "queued",
        )

    def _skip_on_enter_if_resumed(self, state: str) -> bool:
        """Skip the first on_enter callback when resuming from DB.

        In async mode python-statemachine requires `await sm.activate_initial_state()`
        to initialize `current_state`. When we resume an existing MR from DB, that
        activation would re-trigger on_enter_<state>() callbacks (duplicate
        notifications and metadata overwrites). We skip the very first on_enter
        callback once, while still activating the machine.
        """
        if not self._skip_initial_enter:
            return False
        log.debug("Skipping on_enter for resumed state machine", mr_iid=self.mr_iid, state=state)
        self._skip_initial_enter = False
        return True

    # =========================================================================
    # Async Callbacks (MANDATORY per ADR-006)
    # =========================================================================

    async def on_enter_queued(self) -> None:
        """Called when MR enters queued state."""
        if self._skip_on_enter_if_resumed("queued"):
            return
        if getattr(self, "_suppress_queued_notification", False):
            self._suppress_queued_notification = False
            return
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
        if self._skip_on_enter_if_resumed("rebasing"):
            return
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
            await self.websocket_manager.broadcast_mr_status_changed(self.mr_iid, "queued", "rebasing")

    async def on_enter_testing(self) -> None:
        """Called when pipeline starts after rebase."""
        if self._skip_on_enter_if_resumed("testing"):
            return
        log.debug("Entering testing state", mr_iid=self.mr_iid)

        pipeline_id = self._context.get("pipeline_id")
        pipeline_url = self._context.get("pipeline_url")
        expected_sha = self._context.get("expected_sha")

        await self.queue_manager.update_mr_state(
            self.mr_iid,
            "testing",
            pipeline_id=pipeline_id,
            pipeline_status="running",
            expected_sha=expected_sha,
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
            await self.websocket_manager.broadcast_mr_status_changed(self.mr_iid, "rebasing", "testing")

    async def on_enter_merging(self) -> None:
        """Called when pipeline passes and merge starts."""
        if self._skip_on_enter_if_resumed("merging"):
            return
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
            await self.websocket_manager.broadcast_mr_status_changed(self.mr_iid, "testing", "merging")

    async def on_enter_merged(self) -> None:
        """Called when MR is successfully merged."""
        if self._skip_on_enter_if_resumed("merged"):
            return
        log.debug("Entering merged state", mr_iid=self.mr_iid)

        queue_item = await self.queue_manager.get_queue_item(self.mr_iid)
        duration = self._calculate_duration(queue_item)

        now = datetime.now(UTC)

        await self.notifier.notify(
            self.mr_iid,
            "merged",
            merged_at=now,
            duration=duration,
            target_branch=self.target_branch,
        )

        # Broadcast WebSocket completion
        if self.websocket_manager:
            await self.websocket_manager.broadcast_mr_completed(
                self.mr_iid,
                "merged",
                finished_at=now,
            )

        positions_before, old_total = await self._capture_queue_positions_if_enabled()

        # Move MR to history table
        pipeline_duration = self._context.get("pipeline_duration_seconds")
        await self.queue_manager.complete_mr(
            self.mr_iid,
            status="merged",
            pipeline_duration_seconds=pipeline_duration,
        )

        await self._notify_position_changes_if_any(positions_before, old_total)

        # Remove queue label AFTER complete_mr to prevent race condition:
        # webhook from label removal could arrive before MR is completed
        await self.notifier.remove_queue_label(self.mr_iid)

    async def on_enter_failed(self) -> None:
        """Called when MR fails (conflict, pipeline, timeout)."""
        if self._skip_on_enter_if_resumed("failed"):
            return
        log.debug("Entering failed state", mr_iid=self.mr_iid)

        failure_reason = self._context.get("failure_reason", "unknown")
        error_message = self._context.get("error_message")

        # Choose template based on failure reason
        if failure_reason == "conflict":
            await self.notifier.notify(
                self.mr_iid,
                "conflict",
                failed_at=datetime.now(UTC),
                target_branch=self.target_branch,
                conflicted_files=self._context.get("conflicted_files", []),
                error_message=self._context.get("error_message", ""),
            )
        elif failure_reason == "pipeline_failed":
            await self.notifier.notify(
                self.mr_iid,
                "pipeline_failed",
                pipeline_id=self._context.get("pipeline_id"),
                pipeline_url=self._context.get("pipeline_url"),
                failed_at=datetime.now(UTC),
                retried_jobs=self._context.get("retried_jobs", {}),
                failed_jobs=self._context.get("failed_jobs", []),
            )
        elif failure_reason == "timeout":
            queue_item = await self.queue_manager.get_queue_item(self.mr_iid)
            max_wait_hours = self._context.get("max_wait_hours", 2)
            await self.notifier.notify(
                self.mr_iid,
                "timeout",
                failed_at=datetime.now(UTC),
                duration=self._calculate_duration(queue_item),
                max_wait=max_wait_hours,
            )
        elif failure_reason == "merge_failed":
            await self.notifier.notify(
                self.mr_iid,
                "merge_failed",
                failed_at=datetime.now(UTC),
                error_message=error_message or "Unknown merge error",
            )
        else:
            await self.notifier.notify(
                self.mr_iid,
                "generic_failure",
                failed_at=datetime.now(UTC),
                error_message=error_message or "Unknown error",
            )

        # Broadcast WebSocket completion
        if self.websocket_manager:
            await self.websocket_manager.broadcast_mr_completed(
                self.mr_iid,
                "failed",
                finished_at=datetime.now(UTC),
                failure_reason=error_message,
            )

        positions_before, old_total = await self._capture_queue_positions_if_enabled()

        # Move MR to history table
        # Map internal failure_reason to history status
        history_status = "failed"
        if failure_reason == "conflict":
            history_status = "conflict"
        elif failure_reason == "timeout":
            history_status = "timeout"
        elif failure_reason == "merge_failed":
            history_status = "merge_failed"

        await self.queue_manager.complete_mr(
            self.mr_iid,
            status=history_status,
            failure_reason=error_message,
            pipeline_duration_seconds=self._context.get("pipeline_duration_seconds"),
            pipeline_failed_jobs=self._context.get("failed_jobs"),
        )

        await self._notify_position_changes_if_any(positions_before, old_total)

        # Remove queue label AFTER complete_mr to prevent race condition:
        # webhook from label removal could arrive before MR is completed
        await self.notifier.remove_queue_label(self.mr_iid)

    async def on_enter_removed(self) -> None:
        """Called when MR is removed from queue."""
        if self._skip_on_enter_if_resumed("removed"):
            return
        log.debug("Entering removed state", mr_iid=self.mr_iid)

        removal_reason = self._context.get("removal_reason", "label_removed")
        position = await self.queue_manager.get_queue_position(self.mr_iid)

        if removal_reason == "timeout":
            queue_item = await self.queue_manager.get_queue_item(self.mr_iid)
            max_wait_hours = self._context.get("max_wait_hours", 2)
            await self.notifier.notify(
                self.mr_iid,
                "timeout",
                failed_at=datetime.now(UTC),
                duration=self._calculate_duration(queue_item),
                max_wait=max_wait_hours,
            )
        elif removal_reason == "closed":
            await self.notifier.notify(
                self.mr_iid,
                "removed_closed",
                removed_at=datetime.now(UTC),
            )
        elif removal_reason == "external_merge":
            queue_item = await self.queue_manager.get_queue_item(self.mr_iid)
            duration = self._calculate_duration(queue_item)
            await self.notifier.notify(
                self.mr_iid,
                "merged",
                merged_at=datetime.now(UTC),
                duration=duration,
                target_branch=self.target_branch,
            )
        else:
            previous_state = self._context.get("previous_state", "queued")
            await self.notifier.notify(
                self.mr_iid,
                "removed_label",
                removed_at=datetime.now(UTC),
                position=position or 0,
                previous_state=previous_state,
            )

        # Broadcast WebSocket completion
        if self.websocket_manager:
            ws_status = "merged" if removal_reason == "external_merge" else "removed"
            await self.websocket_manager.broadcast_mr_completed(
                self.mr_iid,
                ws_status,
                finished_at=datetime.now(UTC),
            )

        positions_before, old_total = await self._capture_queue_positions_if_enabled()

        # Move MR to history table
        if removal_reason == "timeout":
            history_status = "timeout"
        elif removal_reason == "external_merge":
            history_status = "merged"
        else:
            history_status = "removed"
        failure_reason = None if removal_reason == "external_merge" else f"Removed: {removal_reason}"
        await self.queue_manager.complete_mr(
            self.mr_iid,
            status=history_status,
            failure_reason=failure_reason,
        )

        await self._notify_position_changes_if_any(positions_before, old_total)

        # Remove queue label AFTER complete_mr to prevent race condition:
        # webhook from label removal could arrive before MR is completed
        if removal_reason in ("closed", "timeout"):
            await self.notifier.remove_queue_label(self.mr_iid)

    async def _capture_queue_positions_if_enabled(self) -> tuple[dict[int, int], int]:
        """Capture current queue positions before MR completion for later notification."""
        if self.position_notifier:
            positions_before = await self.position_notifier.capture_queue_positions()
            old_total = await self.queue_manager.get_queue_length()
            return positions_before, old_total
        return {}, 0

    async def _notify_position_changes_if_any(self, positions_before: dict[int, int], old_total: int) -> None:
        """Notify affected MRs about queue position changes after this MR is completed."""
        if self.position_notifier and positions_before:
            await self.position_notifier.notify_affected_mrs_after_completion(
                self.mr_iid,
                positions_before,
                old_total,
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
        expected_sha: str | None = None,
    ) -> None:
        """Rebase completed, pipeline started.

        Args:
            pipeline_id: ID of the new pipeline.
            pipeline_url: URL to the pipeline page.
            expected_sha: SHA that the pipeline should be for (race condition prevention).
        """
        log.info(
            "Triggering rebase_complete",
            mr_iid=self.mr_iid,
            pipeline_id=pipeline_id,
            expected_sha=expected_sha[:8] if expected_sha else None,
        )
        self._context["pipeline_id"] = pipeline_id
        self._context["pipeline_url"] = pipeline_url
        self._context["expected_sha"] = expected_sha
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
        self._context = {
            "failure_reason": "conflict",
            "conflicted_files": conflicted_files,
            "error_message": error_message,
        }
        await self.rebase_failed()

    async def trigger_conflict_during_testing(
        self,
        *,
        conflicted_files: list[str],
        error_message: str,
    ) -> None:
        """Conflict detected during testing (rebase failed while pipeline running).

        Uses pipeline_failed transition (testing→failed) since rebase_failed
        only works from rebasing state.

        Args:
            conflicted_files: List of files with conflicts.
            error_message: Error message for logging.
        """
        log.info(
            "Triggering conflict during testing",
            mr_iid=self.mr_iid,
            conflicted_files=conflicted_files,
        )
        self._context = {
            "failure_reason": "conflict",
            "conflicted_files": conflicted_files,
            "error_message": error_message,
        }
        await self.pipeline_failed()

    async def trigger_pipeline_success(self) -> None:
        """Pipeline passed, proceed to merge."""
        log.info("Triggering pipeline_success", mr_iid=self.mr_iid)
        await self.pipeline_success()

    async def trigger_pipeline_failed(
        self,
        *,
        failed_jobs: list[str],
        retried_jobs: dict[str, int],
        error_message: str,
    ) -> None:
        """Pipeline failed after job retries exhausted.

        Args:
            failed_jobs: List of failed job names.
            retried_jobs: Per-job retry counts {job_name: count}.
            error_message: Error message for logging.
        """
        log.info(
            "Triggering pipeline_failed",
            mr_iid=self.mr_iid,
            failed_jobs=failed_jobs,
            retried_jobs=retried_jobs,
        )
        self._context["failure_reason"] = "pipeline_failed"
        self._context["failed_jobs"] = failed_jobs
        self._context["retried_jobs"] = retried_jobs
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
        self._context = {
            "failure_reason": "merge_failed",
            "error_message": error_message,
        }
        await self.merge_failed()

    async def trigger_reset_to_queued(self, *, error_message: str) -> None:
        """Reset MR to queued after unexpected error for re-processing."""
        log.info("Triggering reset_to_queued", mr_iid=self.mr_iid, error=error_message)
        self._suppress_queued_notification = True
        self._context = {}
        await self.reset_to_queued()
        await self.queue_manager.update_mr_state(self.mr_iid, "queued")

    async def trigger_mark_removed(self, *, reason: str = "label_removed") -> None:
        """Remove MR from queue.

        Args:
            reason: Reason for removal - "label_removed", "closed", or "external_merge".
        """
        log.info("Triggering mark_removed", mr_iid=self.mr_iid, reason=reason)
        self._context = {
            "removal_reason": reason,
            "previous_state": self.current_state.id,
        }
        await self.mark_removed()

    async def trigger_timeout(self, *, max_wait_hours: int = 2) -> None:
        """MR timed out.

        Args:
            max_wait_hours: Maximum wait time that was exceeded.
        """
        log.info("Triggering timeout", mr_iid=self.mr_iid, max_wait_hours=max_wait_hours)
        self._context = {
            "failure_reason": "timeout",
            "max_wait_hours": max_wait_hours,
            "error_message": f"Timed out after {max_wait_hours} hours in {self.current_state.id} state",
        }
        # Use appropriate transition based on current state
        current = self.current_state.id
        if current == "rebasing":
            await self.rebase_failed()
        elif current == "testing":
            await self.pipeline_failed()
        elif current == "merging":
            await self.merge_failed()
        elif current == "queued":
            self._context["removal_reason"] = "timeout"
            await self.mark_removed()
        else:
            log.error("Timeout in unexpected state", mr_iid=self.mr_iid, state=current)

    # =========================================================================
    # Special Notification Methods (no state change)
    # =========================================================================

    async def notify_job_retry(
        self,
        *,
        pipeline_id: int,
        pipeline_url: str | None,
        retried_jobs: list[str],
        retried_counts: dict[str, int],
        max_retries: int,
    ) -> None:
        """Notify about job-level retry (pipeline stays running, no state change).

        Args:
            pipeline_id: ID of the pipeline containing retried jobs.
            pipeline_url: URL to the pipeline page.
            retried_jobs: List of job names being retried.
            retried_counts: Per-job retry counts {job_name: count}.
            max_retries: Maximum retry attempts configured.
        """
        log.info("Job retry initiated", mr_iid=self.mr_iid, retried_jobs=retried_jobs)
        await self.notifier.notify(
            self.mr_iid,
            "job_retry",
            pipeline_id=pipeline_id,
            pipeline_url=pipeline_url,
            retried_jobs=retried_jobs,
            retried_counts=retried_counts,
            max_retries=max_retries,
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

    async def notify_rebase_during_testing(
        self,
        *,
        old_pipeline_id: int | None,
        new_pipeline_id: int,
        rebase_count: int,
        max_attempts: int,
        expected_sha: str | None = None,
    ) -> None:
        """Notify about rebase during testing (stays in testing state).

        Called when target branch changes while pipeline is running,
        requiring a rebase and new pipeline.

        Args:
            old_pipeline_id: ID of the cancelled pipeline (may be None).
            new_pipeline_id: ID of the new pipeline after rebase.
            rebase_count: Current rebase attempt number.
            max_attempts: Maximum rebase attempts allowed.
            expected_sha: New SHA after rebase (for race condition prevention).
        """
        log.info(
            "Notifying rebase during testing",
            mr_iid=self.mr_iid,
            old_pipeline_id=old_pipeline_id,
            new_pipeline_id=new_pipeline_id,
            rebase_count=rebase_count,
            max_attempts=max_attempts,
        )

        # Update pipeline_id and expected_sha in DB
        await self.queue_manager.update_mr_state(
            self.mr_iid,
            "testing",
            pipeline_id=new_pipeline_id,
            pipeline_status="running",
            expected_sha=expected_sha,
        )

        # Build pipeline URL
        pipeline_url = await self.notifier.build_pipeline_url(new_pipeline_id)

        # Update context
        self._context["pipeline_id"] = new_pipeline_id
        self._context["pipeline_url"] = pipeline_url
        self._context["expected_sha"] = expected_sha

        await self.notifier.notify(
            self.mr_iid,
            "rebase_during_testing",
            old_pipeline_id=old_pipeline_id,
            pipeline_id=new_pipeline_id,
            pipeline_url=pipeline_url,
            rebase_count=rebase_count,
            max_attempts=max_attempts,
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _calculate_duration(self, queue_item: QueueItem | None, *, now: datetime | None = None) -> str:
        """Calculate human-readable duration from queued_at to now.

        Delegates to module-level calculate_duration().
        """
        if not queue_item or not queue_item.queued_at:
            return "unknown"
        return calculate_duration(queue_item.queued_at, now=now)


# =============================================================================
# Public Helpers
# =============================================================================


def calculate_duration(queued_at: datetime | None, *, now: datetime | None = None) -> str:
    """Calculate human-readable duration from queued_at to now.

    Args:
        queued_at: Timestamp when MR was queued.
        now: Current time (defaults to datetime.now(UTC)).

    Returns:
        Formatted duration string like "1h 23m" or "45s".
    """
    if queued_at is None:
        return "unknown"

    if now is None:
        now = datetime.now(UTC)

    if queued_at.tzinfo is None:
        log.debug("Normalizing naive datetime to UTC", queued_at=str(queued_at))
        queued_at = queued_at.replace(tzinfo=UTC)

    delta = now - queued_at
    total_seconds = max(0, int(delta.total_seconds()))

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
    notifier: NotifierProtocol,
    queue_manager: QueueManagerProtocol,
    *,
    target_branch: str = "master",
    websocket_manager: WebSocketManager | None = None,
    position_notifier: QueuePositionNotifier | None = None,
) -> StateMachineProtocol:
    """Create state machine for an MR, resuming from DB state if exists.

    Args:
        mr_iid: Merge request IID.
        notifier: Notifier for sending notifications.
        queue_manager: Queue manager for state persistence.
        target_branch: Target branch for rebasing/merging.
        websocket_manager: Optional WebSocketManager for real-time updates.
        position_notifier: Optional QueuePositionNotifier for position change notifications.

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
            position_notifier=position_notifier,
            skip_initial_enter=True,
        )
    else:
        log.debug("Creating new state machine", mr_iid=mr_iid)
        sm = MRStateMachine(
            notifier=notifier,
            queue_manager=queue_manager,
            mr_iid=mr_iid,
            target_branch=target_branch,
            websocket_manager=websocket_manager,
            position_notifier=position_notifier,
        )
    await sm.activate_initial_state()  # type: ignore[no-untyped-call]
    return sm


__all__: list[str] = [
    "MRStateMachine",
    "calculate_duration",
    "create_state_machine_for_mr",
]
