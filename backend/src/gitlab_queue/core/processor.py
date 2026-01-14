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
from enum import Enum
from typing import TYPE_CHECKING

from gitlab_queue.clients.gitlab import (
    GitLabAPIError,
    GitLabCircuitOpenError,
    GitLabConflictError,
    GitLabNotFoundError,
)
from gitlab_queue.core.state_machine import MRStateMachine, create_state_machine_for_mr
from gitlab_queue.metrics import MR_DURATION
from gitlab_queue.utils.logging import LogContext, get_logger

if TYPE_CHECKING:
    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.core.notifier import MRNotifier
    from gitlab_queue.core.queue import QueueManager
    from gitlab_queue.models.pipeline import Pipeline
    from gitlab_queue.models.queue_item import QueueItem

log = get_logger(__name__)


# =============================================================================
# Result Types
# =============================================================================


class ProcessingResult(Enum):
    """Result of processing a single MR."""

    SUCCESS = "success"  # MR merged successfully
    CONFLICT = "conflict"  # Rebase failed due to conflicts
    PIPELINE_FAILED = "pipeline_failed"  # Pipeline failed after retries
    MERGE_FAILED = "merge_failed"  # Merge operation failed
    TIMEOUT = "timeout"  # Operation timed out
    REMOVED = "removed"  # MR removed during processing
    ERROR = "error"  # Unexpected error


@dataclass(frozen=True)
class ProcessingContext:
    """Context for current MR processing."""

    mr_iid: int
    state_machine: MRStateMachine
    start_time: datetime


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

    # Internal state (not part of constructor)
    _shutdown_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _current_mr_iid: int | None = field(default=None, init=False)
    _processing_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

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

        with LogContext(mr_iid=mr_iid, operation="process_mr"):
            try:
                # Create state machine for this MR
                sm = await create_state_machine_for_mr(
                    mr_iid=mr_iid,
                    notifier=self.notifier,
                    queue_manager=self.queue_manager,
                    target_branch=self.settings.target_branch,
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
                result = ProcessingResult.ERROR
                return result
            finally:
                # Record MR processing duration
                duration = (datetime.now(UTC) - start_time).total_seconds()
                MR_DURATION.labels(result=result.value).observe(duration)

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
            # Wait for rebase to complete
            result = await self._wait_for_rebase(ctx)
            if result != ProcessingResult.SUCCESS:
                return result
            current_state = "testing"

        if current_state == "testing":
            # Wait for pipeline
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
    # Rebase Step
    # =========================================================================

    async def _process_rebase(self, ctx: ProcessingContext) -> ProcessingResult:
        """Initiate rebase and wait for completion.

        Args:
            ctx: Processing context.

        Returns:
            ProcessingResult.SUCCESS if rebase completed,
            or appropriate error result.
        """
        mr_iid = ctx.mr_iid
        sm = ctx.state_machine

        log.info("Starting rebase", mr_iid=mr_iid)

        try:
            # Initiate rebase (async operation)
            await self.gitlab_client.rebase_mr(mr_iid)
        except GitLabConflictError as e:
            log.warning("Rebase conflict on initiation", mr_iid=mr_iid, error=str(e))
            # Try to get conflicted files for better reporting
            conflicted_files = await self.gitlab_client.get_mr_conflicts(mr_iid)
            await sm.trigger_rebase_failed(
                conflicted_files=conflicted_files,
                error_message=str(e),
            )
            return ProcessingResult.CONFLICT

        # Wait for rebase to complete
        return await self._wait_for_rebase(ctx)

    async def _wait_for_rebase(self, ctx: ProcessingContext) -> ProcessingResult:
        """Poll rebase status until complete or timeout.

        Args:
            ctx: Processing context.

        Returns:
            ProcessingResult indicating outcome.
        """
        mr_iid = ctx.mr_iid
        sm = ctx.state_machine
        timeout = timedelta(seconds=self.settings.rebase_timeout_seconds)
        start_time = datetime.now(UTC)

        log.debug(
            "Waiting for rebase to complete",
            mr_iid=mr_iid,
            timeout_seconds=timeout.total_seconds(),
        )

        while True:
            # Check shutdown
            if self._shutdown_event.is_set():
                log.info("Shutdown requested during rebase", mr_iid=mr_iid)
                return ProcessingResult.ERROR

            # Check timeout
            elapsed = datetime.now(UTC) - start_time
            if elapsed > timeout:
                log.warning(
                    "Rebase timeout",
                    mr_iid=mr_iid,
                    elapsed_seconds=elapsed.total_seconds(),
                )
                await sm.trigger_timeout(max_wait_hours=max(1, int(timeout.total_seconds() / 3600)))
                return ProcessingResult.TIMEOUT

            # Check rebase status
            rebase_in_progress, has_conflicts = await self.gitlab_client.check_rebase_status(mr_iid)

            if has_conflicts:
                log.warning("Rebase has conflicts", mr_iid=mr_iid)
                # Fetch conflicted files for detailed reporting
                conflicted_files = await self.gitlab_client.get_mr_conflicts(mr_iid)
                await sm.trigger_rebase_failed(
                    conflicted_files=conflicted_files,
                    error_message="Rebase failed due to merge conflicts",
                )
                return ProcessingResult.CONFLICT

            if not rebase_in_progress:
                log.info("Rebase completed", mr_iid=mr_iid)

                # Get the new pipeline that should have started
                pipeline = await self.gitlab_client.get_latest_mr_pipeline(mr_iid)
                if pipeline:
                    pipeline_url = self.notifier.build_pipeline_url(pipeline.id)
                    await sm.trigger_rebase_complete(
                        pipeline_id=pipeline.id,
                        pipeline_url=pipeline_url,
                    )
                    return ProcessingResult.SUCCESS

                # Pipeline not started yet, wait a bit and retry
                log.debug("Waiting for pipeline to start after rebase", mr_iid=mr_iid)

            # Poll interval (shorter than main loop)
            await self._interruptible_sleep(5)

    # =========================================================================
    # Pipeline Step
    # =========================================================================

    async def _handle_pipeline_failure_retry(
        self,
        ctx: ProcessingContext,
        pipeline: Pipeline,
        failed_jobs: list[str],
        retry_count: int,
        max_retries: int,
    ) -> tuple[bool, datetime | None]:
        """Handle pipeline failure with potential retry.

        Returns:
            Tuple of (should_continue, new_start_time). If should_continue is True,
            the pipeline wait loop should continue with the new start time.
        """
        mr_iid = ctx.mr_iid
        sm = ctx.state_machine

        if retry_count >= max_retries:
            await sm.trigger_pipeline_failed(
                failed_jobs=failed_jobs,
                retry_count=retry_count,
                error_message=f"Pipeline {pipeline.status}",
            )
            return False, None

        log.info("Retrying pipeline", mr_iid=mr_iid, retry_count=retry_count + 1)

        old_pipeline_id = pipeline.id
        old_pipeline_url = self.notifier.build_pipeline_url(old_pipeline_id)

        try:
            await self.gitlab_client.rebase_mr(mr_iid)
            await self._wait_for_rebase_quick(ctx)
        except (GitLabConflictError, GitLabAPIError) as e:
            log.exception("Retry rebase failed", mr_iid=mr_iid, error=str(e))
            await sm.trigger_pipeline_failed(
                failed_jobs=failed_jobs,
                retry_count=retry_count + 1,
                error_message=str(e),
            )
            return False, None

        new_pipeline = await self.gitlab_client.get_latest_mr_pipeline(mr_iid)
        if new_pipeline and new_pipeline.id != old_pipeline_id:
            new_pipeline_url = self.notifier.build_pipeline_url(new_pipeline.id)
            await sm.notify_pipeline_retry(
                old_pipeline_id=old_pipeline_id,
                old_pipeline_url=old_pipeline_url,
                new_pipeline_id=new_pipeline.id,
                new_pipeline_url=new_pipeline_url,
                retry_count=retry_count + 1,
                max_retries=max_retries,
                failed_jobs=failed_jobs,
            )
            return True, datetime.now(UTC)

        return False, None

    async def _wait_for_pipeline(self, ctx: ProcessingContext) -> ProcessingResult:
        """Poll pipeline status until success/failure or timeout."""
        mr_iid = ctx.mr_iid
        sm = ctx.state_machine
        timeout = timedelta(seconds=self.settings.pipeline_timeout_seconds)
        start_time = datetime.now(UTC)
        retry_count = 0
        max_retries = self.settings.pipeline_retry_count

        log.info("Waiting for pipeline", mr_iid=mr_iid, timeout_seconds=timeout.total_seconds())

        while True:
            if self._shutdown_event.is_set():
                log.info("Shutdown requested during pipeline wait", mr_iid=mr_iid)
                return ProcessingResult.ERROR

            elapsed = datetime.now(UTC) - start_time
            if elapsed > timeout:
                log.warning(
                    "Pipeline timeout", mr_iid=mr_iid, elapsed_seconds=elapsed.total_seconds()
                )
                await sm.trigger_timeout(max_wait_hours=int(timeout.total_seconds() / 3600))
                return ProcessingResult.TIMEOUT

            if not await self._verify_mr_in_queue(mr_iid):
                await sm.trigger_mark_removed(reason="label_removed")
                return ProcessingResult.REMOVED

            pipeline = await self.gitlab_client.get_latest_mr_pipeline(mr_iid)
            if pipeline is None:
                log.warning("No pipeline found", mr_iid=mr_iid)
                await self._interruptible_sleep(self.settings.poll_interval_seconds)
                continue

            log.debug(
                "Pipeline status", mr_iid=mr_iid, pipeline_id=pipeline.id, status=pipeline.status
            )

            if pipeline.status == "success":
                log.info("Pipeline succeeded", mr_iid=mr_iid, pipeline_id=pipeline.id)
                await sm.trigger_pipeline_success()
                return ProcessingResult.SUCCESS

            if pipeline.status in ("failed", "canceled"):
                failed_jobs = await self._get_failed_jobs(pipeline.id)
                log.warning(
                    "Pipeline failed",
                    mr_iid=mr_iid,
                    pipeline_id=pipeline.id,
                    pipeline_status=pipeline.status,
                    failed_jobs=failed_jobs,
                    retry_count=retry_count,
                    max_retries=max_retries,
                )

                should_continue, new_start = await self._handle_pipeline_failure_retry(
                    ctx, pipeline, failed_jobs, retry_count, max_retries
                )
                if should_continue and new_start:
                    retry_count += 1
                    start_time = new_start
                    continue
                return ProcessingResult.PIPELINE_FAILED

            await self._interruptible_sleep(self.settings.poll_interval_seconds)

    async def _wait_for_rebase_quick(self, ctx: ProcessingContext) -> None:
        """Wait for rebase with a short timeout (for retry scenarios).

        Args:
            ctx: Processing context.

        Raises:
            GitLabAPIError: If rebase times out or fails.
        """
        mr_iid = ctx.mr_iid
        timeout = timedelta(seconds=60)  # Short timeout for retry rebase
        start_time = datetime.now(UTC)

        while True:
            elapsed = datetime.now(UTC) - start_time
            if elapsed > timeout:
                raise GitLabAPIError("Rebase timeout during retry")

            rebase_in_progress, has_conflicts = await self.gitlab_client.check_rebase_status(mr_iid)

            if has_conflicts:
                # Fetch conflicted files for better error reporting
                conflicted_files = await self.gitlab_client.get_mr_conflicts(mr_iid)
                files_info = f": {conflicted_files}" if conflicted_files else ""
                raise GitLabConflictError(f"Rebase conflict during retry{files_info}")

            if not rebase_in_progress:
                return

            await asyncio.sleep(3)

    async def _get_failed_jobs(self, pipeline_id: int) -> list[str]:
        """Get list of failed job names from a pipeline.

        Args:
            pipeline_id: Pipeline ID to check.

        Returns:
            List of failed job names (may be empty).
        """
        try:
            jobs = await self.gitlab_client.get_pipeline_jobs(pipeline_id)
            failed_jobs = [job.name for job in jobs if job.status in ("failed", "canceled")]
            if failed_jobs:
                log.info(
                    "Found failed jobs in pipeline",
                    pipeline_id=pipeline_id,
                    failed_jobs=failed_jobs,
                    count=len(failed_jobs),
                )
            return failed_jobs
        except Exception as e:
            log.warning(
                "Failed to fetch pipeline jobs",
                pipeline_id=pipeline_id,
                error=str(e),
            )
            return []

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

        log.info("Executing merge", mr_iid=mr_iid)

        try:
            # Add 30-second timeout for merge operation to prevent hanging
            merged_mr = await asyncio.wait_for(
                self.gitlab_client.merge_mr(mr_iid),
                timeout=30.0,
            )
            log.info("Merge successful", mr_iid=mr_iid, state=merged_mr.state)
            await sm.trigger_merge_success()
            return ProcessingResult.SUCCESS

        except TimeoutError:
            log.warning("Merge operation timeout", mr_iid=mr_iid)
            await sm.trigger_timeout(max_wait_hours=0)  # 0 indicates merge timeout
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
                    sm = await create_state_machine_for_mr(
                        mr_iid=item.mr_iid,
                        notifier=self.notifier,
                        queue_manager=self.queue_manager,
                        target_branch=self.settings.target_branch,
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
            # Event was set - shutdown requested
            return False
        except TimeoutError:
            # Normal timeout - sleep completed
            return True

    async def _verify_mr_in_queue(self, mr_iid: int) -> bool:
        """Verify MR still has queue label and is open.

        Args:
            mr_iid: MR IID to verify.

        Returns:
            True if MR is still valid for processing.
        """
        try:
            mr = await self.gitlab_client.get_mr(mr_iid)

            if mr.state != "opened":
                log.info("MR is no longer open", mr_iid=mr_iid, state=mr.state)
                return False

            if self.settings.queue_label not in mr.labels:
                log.info("MR no longer has queue label", mr_iid=mr_iid)
                return False

            return True

        except GitLabNotFoundError:
            log.warning("MR not found", mr_iid=mr_iid)
            return False

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
                    # Already merged - update DB
                    await self.queue_manager.update_mr_state(item.mr_iid, "merged")
                    log.info("MR was already merged", mr_iid=item.mr_iid)

                elif mr.state != "opened":
                    # MR closed - mark as removed
                    await self.queue_manager.update_mr_state(item.mr_iid, "removed")
                    log.info("MR was closed", mr_iid=item.mr_iid)

                elif self.settings.queue_label not in mr.labels:
                    # Label removed - mark as removed (orphaned entry cleanup)
                    await self.queue_manager.update_mr_state(item.mr_iid, "removed")
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
                await self.queue_manager.update_mr_state(item.mr_iid, "removed")
                log.warning("MR not found during recovery", mr_iid=item.mr_iid)

            except GitLabAPIError as e:
                log.warning(
                    "GitLab API error during recovery, skipping MR",
                    mr_iid=item.mr_iid,
                    error=str(e),
                )
                continue

        log.info("State recovery complete")

    async def _sync_missing_mrs_from_gitlab(self) -> None:
        """Add MRs that have the queue label in GitLab but aren't in the queue.

        This handles the case where MRs were labeled while the processor was down.

        Gracefully handles GitLab unavailability - if GitLab is down,
        skips sync and lets the scheduler handle it when GitLab recovers.
        """
        log.info("Syncing missing MRs from GitLab")

        # Get all open MRs with queue label from GitLab
        try:
            gitlab_mrs = await self.gitlab_client.list_mrs_with_label(
                self.settings.queue_label,
                state="opened",
            )
        except GitLabCircuitOpenError:
            log.warning("GitLab circuit open, skipping initial sync")
            return
        except GitLabAPIError as e:
            log.warning("Failed to fetch MRs from GitLab during sync", error=str(e))
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
            await asyncio.wait_for(
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
) -> MergeProcessor:
    """Create a configured MergeProcessor instance.

    Args:
        gitlab_client: GitLab API client.
        queue_manager: Queue manager for MR storage.
        notifier: Notifier for MR comments.
        settings: Application settings.

    Returns:
        Configured MergeProcessor ready to run.
    """
    return MergeProcessor(
        gitlab_client=gitlab_client,
        queue_manager=queue_manager,
        notifier=notifier,
        settings=settings,
    )


__all__: list[str] = [
    "MergeProcessor",
    "ProcessingContext",
    "ProcessingResult",
    "create_processor",
]
