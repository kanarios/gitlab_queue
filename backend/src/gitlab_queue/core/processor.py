"""Main Processor Loop for GitLab Merge Queue Bot.

Orchestrates the merge queue workflow:
1. Get next MR from queue
2. Execute rebase via GitLab API
3. Wait for pipeline completion
4. Execute merge or handle errors

The processor runs continuously until shutdown, handling errors gracefully
without stopping the main loop.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from gitlab_queue.clients.gitlab import (
    GitLabAPIError,
    GitLabCircuitOpenError,
    GitLabConflictError,
    GitLabNotFoundError,
)
from gitlab_queue.core.handler_utils import interruptible_sleep, verify_mr_in_queue
from gitlab_queue.core.polling import poll_until_done
from gitlab_queue.core.state_machine import create_state_machine_for_mr
from gitlab_queue.core.types import ProcessingContext, ProcessingResult, RetrySignal
from gitlab_queue.metrics import MR_DURATION
from gitlab_queue.utils.logging import LogContext, get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from gitlab_queue.api.websocket import WebSocketManager
    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.core.notifier import MRNotifier
    from gitlab_queue.core.pipeline_handler import PipelineHandler
    from gitlab_queue.core.protocols import StateMachineFactoryProtocol, StateMachineProtocol
    from gitlab_queue.core.queue import QueueManager
    from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier
    from gitlab_queue.core.rebase_handler import RebaseHandler
    from gitlab_queue.models.mr import MergeRequest
    from gitlab_queue.models.pipeline import Pipeline
    from gitlab_queue.models.queue_item import QueueItem

log = get_logger(__name__)


# =============================================================================
# Main Processor
# =============================================================================


@dataclass
class MergeProcessor:
    """Main processor for the GitLab Merge Queue.

    Orchestrates the merge queue workflow:
    1. Gets next MR from queue
    2. Executes rebase via GitLab API
    3. Waits for pipeline completion
    4. Executes merge or handles errors
    5. Loops continuously with graceful shutdown support

    Example:
        >>> processor = MergeProcessor(gitlab_client, queue_manager, notifier, settings)
        >>> # Start processing in background
        >>> task = asyncio.create_task(processor.run())
        >>> # ... later, to stop
        >>> processor.request_shutdown()
        >>> await task
    """

    gitlab_client: GitLabClient
    queue_manager: QueueManager
    notifier: MRNotifier
    settings: Settings
    position_notifier: QueuePositionNotifier | None = None
    state_machine_factory: StateMachineFactoryProtocol = field(default=create_state_machine_for_mr)
    poll_fn: Callable[..., Any] = field(default=poll_until_done)
    wait_for_fn: Callable[..., Any] = field(default=asyncio.wait_for)
    sleep_fn: Callable[[float], Awaitable[bool]] | None = field(default=None)

    # Internal state (not part of constructor)
    _shutdown_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _current_mr_iid: int | None = field(default=None, init=False)
    _processing_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _websocket_manager: WebSocketManager | None = field(default=None, init=False)
    _ph: PipelineHandler | None = field(default=None, repr=False)
    _rh: RebaseHandler | None = field(default=None, repr=False)

    @property
    def _pipeline_handler(self) -> PipelineHandler:
        """Lazy-cached PipelineHandler.

        Created on first access so tests that replace processor attributes
        after creation still work. Cached so tests can patch handler methods.
        """
        if self._ph is None:
            from gitlab_queue.core.pipeline_handler import PipelineHandler

            self._ph = PipelineHandler(
                gitlab_client=self.gitlab_client,
                queue_manager=self.queue_manager,
                notifier=self.notifier,
                settings=self.settings,
                shutdown_event=self._shutdown_event,
            )
        return self._ph

    @property
    def _rebase_handler(self) -> RebaseHandler:
        """Lazy-cached RebaseHandler."""
        if self._rh is None:
            from gitlab_queue.core.rebase_handler import RebaseHandler

            self._rh = RebaseHandler(
                gitlab_client=self.gitlab_client,
                notifier=self.notifier,
                settings=self.settings,
                shutdown_event=self._shutdown_event,
                poll_fn=self.poll_fn,
            )
        return self._rh

    def set_websocket_manager(self, manager: WebSocketManager) -> None:
        """Set WebSocket manager for broadcasting queue updates.

        Args:
            manager: WebSocketManager instance.
        """
        self._websocket_manager = manager
        log.debug("WebSocket manager set for processor")

    # =========================================================================
    # Main Loop
    # =========================================================================

    async def run(self) -> None:
        """Main processing loop - runs until shutdown signal.

        This is the entry point for starting the processor.
        Runs continuously, processing MRs from the queue until
        shutdown is requested via request_shutdown().
        """
        log.info("Merge processor starting")

        try:
            # Recovery on startup: clean up interrupted state and sync with GitLab
            await self._recover_interrupted_state()
            await self._sync_missing_mrs_from_gitlab()

            while not self._shutdown_event.is_set():
                try:
                    await self._process_iteration()
                except GitLabCircuitOpenError as e:
                    # Circuit breaker is open - wait before retrying
                    wait_time = e.retry_after or 30
                    log.warning(
                        "GitLab API circuit open, pausing processing",
                        retry_after=wait_time,
                    )
                    if not await self._interruptible_sleep(wait_time):
                        break  # Shutdown requested during sleep
                    continue  # Skip normal sleep, go to next iteration
                except Exception as e:
                    # Errors don't stop the loop
                    log.exception("Iteration failed", error=str(e))

                # Cancellable sleep between iterations
                if not await self._interruptible_sleep(self.settings.poll_interval_seconds):
                    break  # Shutdown requested during sleep
        finally:
            log.info("Merge processor stopped")

    async def _process_iteration(self) -> None:
        """Execute one iteration of the processing loop."""
        log.debug("Processing iteration started")

        # Check for stale MRs and send warnings
        await self._check_stale_mrs()

        # Get next MR from queue
        queue_item = await self.queue_manager.get_next_mr()

        if queue_item is None:
            log.debug("Queue empty, waiting for next iteration")
            return

        log.info("Processing MR", mr_iid=queue_item.mr_iid, title=queue_item.title)

        async with self._processing_lock:
            self._current_mr_iid = queue_item.mr_iid
            try:
                result = await self._process_mr(queue_item)
                log.info(
                    "MR processing completed",
                    mr_iid=queue_item.mr_iid,
                    result=result.value,
                )
            finally:
                self._current_mr_iid = None

    # =========================================================================
    # MR Processing
    # =========================================================================

    async def _process_mr(self, queue_item: QueueItem) -> ProcessingResult:
        """Process a single MR through the full workflow.

        Workflow:
        1. Create state machine (resume from current state if interrupted)
        2. Execute rebase
        3. Wait for pipeline
        4. Execute merge

        Args:
            queue_item: The queue item to process.

        Returns:
            ProcessingResult indicating the outcome.
        """
        mr_iid = queue_item.mr_iid
        start_time = datetime.now(UTC)
        result = ProcessingResult.ERROR  # Default for unexpected exits

        sm: StateMachineProtocol | None = None

        with LogContext(mr_iid=mr_iid, operation="process_mr"):
            try:
                # Create state machine for this MR
                sm = await self.state_machine_factory(
                    mr_iid=mr_iid,
                    notifier=self.notifier,
                    queue_manager=self.queue_manager,
                    target_branch=self.settings.target_branch,
                    websocket_manager=self._websocket_manager,
                    position_notifier=self.position_notifier,
                )

                ctx = ProcessingContext(
                    mr_iid=mr_iid,
                    state_machine=sm,
                    start_time=start_time,
                )

                # Check if MR still has the queue label
                if not await self._verify_mr_in_queue(mr_iid):
                    await sm.trigger_mark_removed(reason="label_removed")
                    result = ProcessingResult.REMOVED
                    return result

                # Execute workflow based on current state
                result = await self._execute_workflow(ctx)
                return result

            except asyncio.CancelledError:
                log.warning("MR processing cancelled", mr_iid=mr_iid)
                raise
            except Exception as e:
                log.exception("Unexpected error processing MR", mr_iid=mr_iid, error=str(e))
                try:
                    await self._handle_processing_error(mr_iid, e, sm)
                except Exception as requeue_err:
                    log.exception("Failed to reset MR state", mr_iid=mr_iid, error=str(requeue_err))
                result = ProcessingResult.ERROR
                return result
            finally:
                # Record MR processing duration
                duration = (datetime.now(UTC) - start_time).total_seconds()
                MR_DURATION.labels(result=result.value).observe(duration)

    async def _handle_processing_error(
        self,
        mr_iid: int,
        error: Exception,
        sm: StateMachineProtocol | None,
    ) -> None:
        """Handle error recovery: increment attempts, requeue or fail permanently."""
        queue_item_now = await self.queue_manager.get_queue_item(mr_iid)
        if queue_item_now is None:
            log.warning("MR no longer in queue during error recovery", mr_iid=mr_iid)
            return

        attempts = queue_item_now.processing_attempts + 1

        if attempts >= self.settings.max_processing_attempts:
            log.warning(
                "MR exceeded max processing attempts, failing permanently",
                mr_iid=mr_iid,
                attempts=attempts,
                max_attempts=self.settings.max_processing_attempts,
            )
            error_msg = f"MR permanently failed after {attempts} attempts. Last error: {error}"
            if sm is not None:
                await self._fail_mr_permanently(sm, mr_iid, error_msg)
            else:
                await self.queue_manager.complete_mr(
                    mr_iid,
                    status="failed",
                    failure_reason=error_msg,
                )
                await self.notifier.notify(
                    mr_iid,
                    "generic_failure",
                    error_message=error_msg,
                )
                await self.notifier.remove_queue_label(mr_iid)
            return

        if sm is not None:
            await sm.trigger_reset_to_queued(error_message=str(error))
        await self.queue_manager.update_mr_state(
            mr_iid,
            "queued",
            processing_attempts=attempts,
        )
        log.info("Reset MR to queued after error", mr_iid=mr_iid, attempt=attempts)

    async def _execute_workflow(self, ctx: ProcessingContext) -> ProcessingResult:
        """Execute the full workflow for an MR based on its current state.

        Args:
            ctx: Processing context with MR and state machine.

        Returns:
            ProcessingResult indicating the outcome.
        """
        sm = ctx.state_machine
        current_state = sm.current_state.id

        # Resume from current state
        if current_state == "queued":
            # Start processing - transition to rebasing
            await sm.trigger_start_processing()
            result = await self._process_rebase(ctx)
            if result != ProcessingResult.SUCCESS:
                return result
            current_state = "testing"

        if current_state == "rebasing":
            # Capture pre-rebase SHA if not already set (e.g., restart recovery)
            await self._capture_pre_rebase_state(ctx)
            # Wait for rebase to complete
            result = await self._wait_for_rebase(ctx)
            if result != ProcessingResult.SUCCESS:
                return result
            current_state = "testing"

        if current_state == "testing":
            # Reset attempts on entering testing — MR made progress (rebase succeeded).
            # Zycling protection during pipeline wait is handled by pipeline_timeout_seconds.
            await self.queue_manager.update_mr_state(
                ctx.mr_iid,
                "testing",
                processing_attempts=0,
            )
            result = await self._wait_for_pipeline(ctx)
            if result != ProcessingResult.SUCCESS:
                return result
            current_state = "merging"

        if current_state == "merging":
            return await self._process_merge(ctx)

        # Unexpected state
        log.warning("Unexpected state in workflow", state=current_state, mr_iid=ctx.mr_iid)
        return ProcessingResult.ERROR

    # =========================================================================
    # Rebase Step (delegated to RebaseHandler)
    # =========================================================================

    async def _process_rebase(self, ctx: ProcessingContext) -> ProcessingResult:
        return await self._rebase_handler.process_rebase(ctx)

    async def _wait_for_rebase(self, ctx: ProcessingContext) -> ProcessingResult:
        return await self._rebase_handler.wait_for_rebase(ctx)

    async def _wait_for_pipeline(self, ctx: ProcessingContext) -> ProcessingResult:
        return await self._pipeline_handler.wait_for_pipeline(ctx)

    async def _wait_for_rebase_quick(self, ctx: ProcessingContext) -> None:
        return await self._rebase_handler.wait_for_rebase_quick(ctx)

    async def _should_skip_stale_pipeline(self, mr_iid: int, pipeline: Pipeline) -> bool:
        return await self._pipeline_handler.should_skip_stale_pipeline(mr_iid, pipeline)

    async def _check_pipeline_termination_conditions(
        self,
        ctx: ProcessingContext,
        sm: StateMachineProtocol,
        timeout: timedelta,
        start_time: datetime,
    ) -> ProcessingResult | None:
        return await self._pipeline_handler.check_pipeline_termination_conditions(ctx, sm, timeout, start_time)

    async def _handle_pipeline_failure_retry(
        self,
        ctx: ProcessingContext,
        pipeline: Pipeline,
        retried_jobs: dict[str, int],
    ) -> tuple[bool, datetime | None, dict[str, int]]:
        return await self._pipeline_handler.handle_pipeline_failure_retry(ctx, pipeline, retried_jobs)

    async def _handle_pipeline_failure(
        self,
        ctx: ProcessingContext,
        pipeline: Pipeline,
        retried_jobs: dict[str, int],
    ) -> ProcessingResult | RetrySignal:
        return await self._pipeline_handler.handle_pipeline_failure(ctx, pipeline, retried_jobs)

    async def _handle_pipeline_status(
        self,
        ctx: ProcessingContext,
        sm: StateMachineProtocol,
        pipeline: Pipeline,
        retried_jobs: dict[str, int],
    ) -> ProcessingResult | RetrySignal | None:
        return await self._pipeline_handler.handle_pipeline_status(ctx, sm, pipeline, retried_jobs)

    # =========================================================================
    # Merge Step
    # =========================================================================

    async def _process_merge(self, ctx: ProcessingContext) -> ProcessingResult:
        """Execute the merge operation.

        Args:
            ctx: Processing context.

        Returns:
            ProcessingResult indicating outcome.
        """
        mr_iid = ctx.mr_iid
        sm = ctx.state_machine

        # Get expected SHA from queue item for race condition detection
        queue_item = await self.queue_manager.get_queue_item(mr_iid)
        expected_sha = queue_item.expected_sha if queue_item else None

        log.info("Executing merge", mr_iid=mr_iid, expected_sha=expected_sha[:8] if expected_sha else None)

        try:
            # Add timeout for merge operation to prevent hanging
            merged_mr = await self.wait_for_fn(
                self.gitlab_client.merge_mr(mr_iid, expected_sha=expected_sha),
                timeout=float(self.settings.merge_timeout_seconds),
            )
            log.info("Merge successful", mr_iid=mr_iid, state=merged_mr.state)
            await sm.trigger_merge_success()
            return ProcessingResult.SUCCESS

        except TimeoutError:
            log.warning("Merge operation timeout", mr_iid=mr_iid)
            await sm.trigger_merge_failed(
                error_message=f"Merge operation timed out after {self.settings.merge_timeout_seconds} seconds",
            )
            return ProcessingResult.TIMEOUT

        except GitLabConflictError as e:
            log.warning("Merge conflict", mr_iid=mr_iid, error=str(e))
            await sm.trigger_merge_failed(error_message=str(e))
            return ProcessingResult.MERGE_FAILED

        except GitLabAPIError as e:
            log.exception("Merge API error", mr_iid=mr_iid, error=str(e))
            await sm.trigger_merge_failed(error_message=str(e))
            return ProcessingResult.MERGE_FAILED

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _fail_mr_permanently(
        self,
        sm: StateMachineProtocol,
        mr_iid: int,
        error_message: str,
    ) -> None:
        """Transition MR to failed state using the appropriate trigger.

        For rebasing/testing/merging states, the corresponding SM trigger is called.
        These triggers handle notifications via on_enter_failed() callback —
        no explicit notify() call is needed here.

        The else branch handles unexpected states where the SM cannot transition,
        so it calls notify() and complete_mr() directly as a fallback.
        """
        current = sm.current_state.id
        if current == "rebasing":
            await sm.trigger_rebase_failed(
                conflicted_files=[],
                error_message=error_message,
            )
        elif current == "testing":
            await sm.trigger_pipeline_failed(
                failed_jobs=[],
                retried_jobs={},
                error_message=error_message,
            )
        elif current == "merging":
            await sm.trigger_merge_failed(error_message=error_message)
        else:
            log.error(
                "Cannot fail MR permanently from unexpected state, using direct completion",
                mr_iid=mr_iid,
                state=current,
            )
            await self.queue_manager.complete_mr(
                mr_iid,
                status="failed",
                failure_reason=error_message,
            )
            await self.notifier.notify(
                mr_iid,
                "generic_failure",
                error_message=error_message,
            )
            await self.notifier.remove_queue_label(mr_iid)

    async def _check_stale_mrs(self) -> None:
        """Check for MRs that have been in queue too long and send warnings.

        Runs periodically to detect MRs exceeding stale_mr_warning_hours.
        Sends a single warning per MR (tracked via stale_warning_sent field).
        """
        warning_hours = self.settings.stale_mr_warning_hours
        stale_items = await self.queue_manager.get_stale_mrs(warning_hours)

        for item in stale_items:
            # Only warn once (check is already done in SQL query, but double-check here)
            if not item.stale_warning_sent:
                try:
                    sm = await self.state_machine_factory(
                        mr_iid=item.mr_iid,
                        notifier=self.notifier,
                        queue_manager=self.queue_manager,
                        target_branch=self.settings.target_branch,
                        websocket_manager=self._websocket_manager,
                        position_notifier=self.position_notifier,
                    )
                    await sm.notify_stale_warning(warning_hours=warning_hours)
                    await self.queue_manager.mark_stale_warning_sent(item.mr_iid)
                    log.info(
                        "Stale MR warning sent",
                        mr_iid=item.mr_iid,
                        warning_hours=warning_hours,
                    )
                except Exception as e:
                    log.exception(
                        "Failed to send stale warning",
                        mr_iid=item.mr_iid,
                        error=str(e),
                    )

    async def _capture_pre_rebase_state(self, ctx: ProcessingContext) -> str:
        return await self._rebase_handler.capture_pre_rebase_state(ctx)

    async def _interruptible_sleep(self, seconds: float) -> bool:
        """Sleep that can be interrupted by shutdown event."""
        if self.sleep_fn is not None:
            return await self.sleep_fn(seconds)
        return await interruptible_sleep(self._shutdown_event, seconds)

    async def _verify_mr_in_queue(self, mr_iid: int) -> bool:
        """Verify MR still has queue label and is open."""
        return await verify_mr_in_queue(self.gitlab_client, self.settings, mr_iid)

    async def _recover_interrupted_state(self) -> None:
        """Recover MRs that were in intermediate states when processor stopped.

        Handles all active states (queued, rebasing, testing, merging):
        - Verifies each MR still exists in GitLab
        - Verifies queue label is still present
        - Marks removed if MR was closed, merged, or label removed
        - Resets intermediate states (rebasing, testing, merging) to queued

        Gracefully handles GitLab unavailability - if GitLab is down,
        skips recovery and lets the scheduler handle sync when GitLab recovers.
        """
        log.info("Checking for interrupted MRs")

        try:
            active_items = await self.queue_manager.get_active_queue()
        except Exception as e:
            log.warning("Failed to get active queue during recovery", error=str(e))
            return

        for item in active_items:
            log.debug(
                "Checking MR state during recovery",
                mr_iid=item.mr_iid,
                state=item.state,
            )

            # Check actual GitLab state for all active MRs
            try:
                mr = await self.gitlab_client.get_mr(item.mr_iid)

                if mr.state == "merged":
                    # Already merged - move to history
                    await self.queue_manager.complete_mr(item.mr_iid, status="merged")
                    log.info("MR was already merged", mr_iid=item.mr_iid)

                elif mr.state != "opened":
                    # MR closed - move to history as removed
                    await self.queue_manager.complete_mr(
                        item.mr_iid,
                        status="removed",
                        failure_reason="closed_during_recovery",
                    )
                    log.info("MR was closed", mr_iid=item.mr_iid)

                elif self.settings.queue_label not in mr.labels and self.settings.hotfix_label not in mr.labels:
                    # Label removed - mark as removed (orphaned entry cleanup)
                    await self.queue_manager.complete_mr(
                        item.mr_iid,
                        status="removed",
                        failure_reason="label_removed",
                    )
                    log.info("MR label was removed", mr_iid=item.mr_iid)

                elif item.state in ("rebasing", "testing", "merging"):
                    # Reset intermediate states to queued for re-processing
                    await self.queue_manager.update_mr_state(item.mr_iid, "queued")
                    log.info(
                        "Reset MR to queued",
                        mr_iid=item.mr_iid,
                        previous_state=item.state,
                    )
                # else: MR is in 'queued' state and still valid - no action needed

            except GitLabCircuitOpenError:
                log.warning(
                    "GitLab circuit open during recovery, skipping MR",
                    mr_iid=item.mr_iid,
                )
                continue

            except GitLabNotFoundError:
                await self.queue_manager.complete_mr(
                    item.mr_iid,
                    status="removed",
                    failure_reason="not_found",
                )
                log.warning("MR not found during recovery", mr_iid=item.mr_iid)

            except GitLabAPIError as e:
                log.warning(
                    "GitLab API error during recovery, skipping MR",
                    mr_iid=item.mr_iid,
                    error=str(e),
                )
                continue

        log.info("State recovery complete")

    async def _fetch_mrs_by_label(self, label: str) -> list[MergeRequest]:
        """Fetch open MRs with a given label, gracefully handling GitLab errors.

        Args:
            label: GitLab label to filter by.

        Returns:
            List of MRs, empty if GitLab is unavailable.
        """
        try:
            return await self.gitlab_client.list_mrs_with_label(label, state="opened")
        except GitLabCircuitOpenError:
            log.warning("GitLab circuit open, skipping label sync", label=label)
        except GitLabAPIError as e:
            log.warning("Failed to fetch MRs from GitLab during sync", label=label, error=str(e))
        return []

    async def _sync_missing_mrs_from_gitlab(self) -> None:
        """Add MRs that have the queue label in GitLab but aren't in the queue.

        This handles the case where MRs were labeled while the processor was down.

        Gracefully handles GitLab unavailability - if GitLab is down,
        skips sync and lets the scheduler handle it when GitLab recovers.
        """
        log.info("Syncing missing MRs from GitLab")

        queue_mrs = await self._fetch_mrs_by_label(self.settings.queue_label)
        hotfix_mrs = await self._fetch_mrs_by_label(self.settings.hotfix_label)

        # Merge without duplicates
        mrs_dict = {mr.iid: mr for mr in queue_mrs}
        for mr in hotfix_mrs:
            if mr.iid not in mrs_dict:
                mrs_dict[mr.iid] = mr
        gitlab_mrs = list(mrs_dict.values())

        if not gitlab_mrs:
            log.info("No MRs found with queue or hotfix labels")
            return

        # Get current queue IIDs
        active_items = await self.queue_manager.get_active_queue()
        queued_iids = {item.mr_iid for item in active_items}

        # Add missing MRs to queue
        added_count = 0
        for mr in gitlab_mrs:
            if mr.iid not in queued_iids:
                is_hotfix = self.settings.hotfix_label in mr.labels
                await self.queue_manager.add_to_queue(mr, is_hotfix=is_hotfix)
                log.info(
                    "Added missing MR to queue",
                    mr_iid=mr.iid,
                    title=mr.title,
                    is_hotfix=is_hotfix,
                )
                added_count += 1

        log.info(
            "GitLab sync complete",
            gitlab_mrs_count=len(gitlab_mrs),
            added_count=added_count,
        )

        # Broadcast queue update if MRs were added
        if added_count > 0 and self._websocket_manager:
            await self._broadcast_queue_update()

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

    # =========================================================================
    # Shutdown Control
    # =========================================================================

    def request_shutdown(self) -> None:
        """Request graceful shutdown of the processor.

        This sets the shutdown event, which will:
        1. Stop accepting new MRs
        2. Complete current MR processing (or abort at safe point)
        3. Exit the main loop
        """
        log.info("Shutdown requested")
        self._shutdown_event.set()

    async def wait_for_shutdown(self, timeout: float | None = None) -> bool:
        """Wait for the processor to complete shutdown.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            True if shutdown completed, False if timeout.
        """
        try:
            await self.wait_for_fn(
                self._shutdown_event.wait(),
                timeout=timeout,
            )
            return True
        except TimeoutError:
            return False

    @property
    def is_processing(self) -> bool:
        """Check if processor is currently processing an MR."""
        return self._current_mr_iid is not None

    @property
    def current_mr_iid(self) -> int | None:
        """Get the IID of the MR currently being processed."""
        return self._current_mr_iid

    @property
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_event.is_set()


# =============================================================================
# Factory Function
# =============================================================================


def create_processor(
    gitlab_client: GitLabClient,
    queue_manager: QueueManager,
    notifier: MRNotifier,
    settings: Settings,
    position_notifier: QueuePositionNotifier | None = None,
) -> MergeProcessor:
    """Create a configured MergeProcessor instance.

    Args:
        gitlab_client: GitLab API client.
        queue_manager: Queue manager for MR storage.
        notifier: Notifier for MR comments.
        settings: Application settings.
        position_notifier: Queue position notifier for position change notifications.

    Returns:
        Configured MergeProcessor ready to run.
    """
    return MergeProcessor(
        gitlab_client=gitlab_client,
        queue_manager=queue_manager,
        notifier=notifier,
        settings=settings,
        position_notifier=position_notifier,
    )


__all__: list[str] = [
    "MergeProcessor",
    "ProcessingResult",
    "create_processor",
]
