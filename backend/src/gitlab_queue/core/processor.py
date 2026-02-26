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
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

from gitlab_queue.clients.gitlab import (
    GitLabAPIError,
    GitLabCircuitOpenError,
    GitLabConflictError,
    GitLabNotFoundError,
)
from gitlab_queue.core.polling import PollingConfig, PollOutcome, PollStatus, poll_until_done
from gitlab_queue.core.rebase_during_testing import (
    RebaseDuringTestingContext,
    RebaseDuringTestingHandler,
    RebaseRetryLimitExceeded,
)
from gitlab_queue.core.state_machine import MRStateMachine, create_state_machine_for_mr
from gitlab_queue.metrics import MR_DURATION
from gitlab_queue.utils.logging import LogContext, get_logger

if TYPE_CHECKING:
    from gitlab_queue.api.websocket import WebSocketManager
    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.core.notifier import MRNotifier
    from gitlab_queue.core.queue import QueueManager
    from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier
    from gitlab_queue.models.mr import MergeRequest
    from gitlab_queue.models.pipeline import Pipeline
    from gitlab_queue.models.queue_item import QueueItem

log = get_logger(__name__)


# =============================================================================
# Constants (eliminates magic numbers)
# =============================================================================

# Polling intervals (seconds)
REBASE_POLL_INTERVAL_SECONDS = 5
QUICK_REBASE_POLL_INTERVAL_SECONDS = 3

# Timeouts (seconds)
QUICK_REBASE_TIMEOUT_SECONDS = 60
DEFAULT_POST_REBASE_PIPELINE_WAIT_SECONDS = 60

# Failed/canceled pipeline statuses to skip in the fast-forward case
# (SHA unchanged after rebase — success pipeline is still valid).
TERMINAL_FAILED_PIPELINE_STATUSES = frozenset(("canceled", "failed"))

# ALL terminal pipeline statuses to skip when SHA changed after rebase.
# After rebase, ANY terminal pipeline (including success) is stale —
# it was started before the rebase and doesn't reflect the new code.
TERMINAL_PIPELINE_STATUSES = frozenset(("canceled", "failed", "success"))


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


@dataclass
class RebaseContext:
    """Context for rebase operation tracking.

    Tracks SHA before rebase to detect race conditions where
    GitLab returns stale pipeline data after rebase completes.
    """

    old_sha: str = ""


@dataclass
class ProcessingContext:
    """Context for current MR processing."""

    mr_iid: int
    state_machine: MRStateMachine
    start_time: datetime
    rebase_ctx: RebaseContext = field(default_factory=RebaseContext)


@dataclass
class RebaseCheckOutcome:
    """Result of checking if rebase is needed during testing.

    Separates success context from error result for clearer API.
    """

    context: RebaseDuringTestingContext | None
    result: ProcessingResult | None
    last_check: datetime
    should_reset: bool


@dataclass
class RetrySignal:
    """Signal to retry pipeline with updated state.

    Used instead of tuple[int, datetime] for type clarity.
    """

    retry_count: int
    new_start_time: datetime


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

    # Internal state (not part of constructor)
    _shutdown_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _current_mr_iid: int | None = field(default=None, init=False)
    _processing_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _websocket_manager: WebSocketManager | None = field(default=None, init=False)

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

        with LogContext(mr_iid=mr_iid, operation="process_mr"):
            try:
                # Create state machine for this MR
                sm = await create_state_machine_for_mr(
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
            # Capture pre-rebase SHA if not already set (e.g., restart recovery)
            await self._capture_pre_rebase_sha(ctx)
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

        # Capture old SHA before rebase for race condition prevention
        await self._capture_pre_rebase_sha(ctx)

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

        log.debug(
            "Waiting for rebase to complete",
            mr_iid=mr_iid,
            timeout_seconds=self.settings.rebase_timeout_seconds,
        )

        async def check_rebase() -> tuple[PollStatus, ProcessingResult | None]:
            """Poll rebase status until complete or conflict detected."""
            rebase_in_progress, has_conflicts = await self.gitlab_client.check_rebase_status(mr_iid)

            if has_conflicts:
                log.warning("Rebase has conflicts", mr_iid=mr_iid)
                conflicted_files = await self.gitlab_client.get_mr_conflicts(mr_iid)
                await sm.trigger_rebase_failed(
                    conflicted_files=conflicted_files,
                    error_message="Rebase failed due to merge conflicts",
                )
                return PollStatus.DONE, ProcessingResult.CONFLICT

            if not rebase_in_progress:
                log.info("Rebase completed", mr_iid=mr_iid)
                old_sha = ctx.rebase_ctx.old_sha
                pipeline, new_sha = await self._wait_for_post_rebase_pipeline(
                    mr_iid, old_sha, timeout_seconds=self.settings.post_rebase_pipeline_wait_seconds
                )

                if pipeline and pipeline.sha == new_sha:
                    pipeline_url = await self.notifier.build_pipeline_url(pipeline.id)
                    await sm.trigger_rebase_complete(
                        pipeline_id=pipeline.id,
                        pipeline_url=pipeline_url,
                        expected_sha=new_sha,
                    )
                    return PollStatus.DONE, ProcessingResult.SUCCESS

                log.debug(
                    "Waiting for pipeline with correct SHA after rebase",
                    mr_iid=mr_iid,
                    expected_sha=new_sha[:8] if new_sha else "unknown",
                )

            return PollStatus.CONTINUE, None

        config = PollingConfig(
            timeout_seconds=self.settings.rebase_timeout_seconds,
            poll_interval_seconds=REBASE_POLL_INTERVAL_SECONDS,
            operation_name="rebase",
        )
        outcome = await poll_until_done(config, check_rebase, self._shutdown_event)

        if outcome.completed and outcome.result:
            return outcome.result

        if outcome.shutdown_requested:
            log.info("Shutdown requested during rebase", mr_iid=mr_iid)
            return ProcessingResult.ERROR

        if outcome.timed_out:
            timeout_hours = max(1, int(self.settings.rebase_timeout_seconds / 3600))
            log.warning(
                "Rebase timeout",
                mr_iid=mr_iid,
                timeout_seconds=self.settings.rebase_timeout_seconds,
            )
            await sm.trigger_timeout(max_wait_hours=timeout_hours)
            return ProcessingResult.TIMEOUT

        return ProcessingResult.ERROR

    async def _wait_for_post_rebase_pipeline(
        self,
        mr_iid: int,
        old_sha: str,
        timeout_seconds: int | None = None,
    ) -> tuple[Pipeline | None, str]:
        """Wait for a new pipeline after rebase with the correct SHA.

        After rebase completes, GitLab may still return an old pipeline
        due to API caching or the new pipeline not yet being created.
        This method waits until we find a pipeline whose SHA matches
        the MR's current (post-rebase) SHA.

        Args:
            mr_iid: MR IID to wait for.
            old_sha: SHA before rebase started.
            timeout_seconds: Maximum time to wait (default 60s).

        Returns:
            Tuple of (pipeline, new_sha). Pipeline may be None if not found.
        """
        if timeout_seconds is None:
            timeout_seconds = DEFAULT_POST_REBASE_PIPELINE_WAIT_SECONDS

        async def check_pipeline() -> tuple[PollStatus, tuple[Pipeline | None, str] | None]:
            """Poll for new pipeline on updated SHA after rebase."""
            mr = await self.gitlab_client.get_mr(mr_iid)

            if mr.rebase_in_progress:
                return PollStatus.CONTINUE, None

            new_sha = mr.sha

            # Fast-forward case: SHA unchanged (no commits ahead of target)
            if new_sha == old_sha:
                pipeline = await self.gitlab_client.get_latest_mr_pipeline(mr_iid)
                if pipeline and pipeline.sha == new_sha:
                    if pipeline.status in TERMINAL_FAILED_PIPELINE_STATUSES:
                        log.info(
                            "Skipping pre-existing terminal pipeline in fast-forward case",
                            mr_iid=mr_iid,
                            pipeline_id=pipeline.id,
                            pipeline_status=pipeline.status,
                        )
                        return PollStatus.CONTINUE, None
                    return PollStatus.DONE, (pipeline, new_sha)
                return PollStatus.CONTINUE, None

            # SHA changed, need pipeline with new SHA
            pipeline = await self.gitlab_client.get_latest_mr_pipeline(mr_iid)
            if pipeline and pipeline.sha == new_sha:
                if pipeline.status in TERMINAL_PIPELINE_STATUSES:
                    log.info(
                        "Skipping pre-existing terminal pipeline after rebase",
                        mr_iid=mr_iid,
                        pipeline_id=pipeline.id,
                        pipeline_status=pipeline.status,
                    )
                    return PollStatus.CONTINUE, None
                log.info(
                    "Found pipeline with new SHA after rebase",
                    mr_iid=mr_iid,
                    pipeline_id=pipeline.id,
                    old_sha=old_sha[:8],
                    new_sha=new_sha[:8],
                )
                return PollStatus.DONE, (pipeline, new_sha)

            return PollStatus.CONTINUE, None

        config = PollingConfig(
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=self.settings.pipeline_poll_interval_seconds,
            operation_name="post_rebase_pipeline",
        )
        outcome: PollOutcome[tuple[Pipeline | None, str]] = await poll_until_done(
            config, check_pipeline, self._shutdown_event
        )

        if outcome.completed and outcome.result:
            return outcome.result

        if outcome.shutdown_requested:
            return None, old_sha

        # Timeout - return current state with SHA validation
        mr = await self.gitlab_client.get_mr(mr_iid)
        new_sha = mr.sha
        pipeline = await self.gitlab_client.get_latest_mr_pipeline(mr_iid)
        log.warning(
            "Timeout waiting for post-rebase pipeline",
            mr_iid=mr_iid,
            old_sha=old_sha[:8],
            current_sha=new_sha[:8] if new_sha else "unknown",
            pipeline_id=pipeline.id if pipeline else None,
            pipeline_sha=pipeline.sha[:8] if pipeline and pipeline.sha else None,
        )

        # Don't return stale pipeline if SHA doesn't match
        if pipeline and pipeline.sha != new_sha:
            log.warning(
                "Timeout with stale pipeline - SHA mismatch",
                mr_iid=mr_iid,
                pipeline_sha=pipeline.sha[:8] if pipeline.sha else "unknown",
                expected_sha=new_sha[:8] if new_sha else "unknown",
            )
            return None, new_sha

        return pipeline, new_sha

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
        old_pipeline_url = await self.notifier.build_pipeline_url(old_pipeline_id)

        # Capture old SHA before retry rebase for race condition prevention
        old_sha = await self._capture_pre_rebase_sha(ctx)

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

        # Wait for new pipeline with correct SHA using the robust method
        timeout_seconds = self.settings.post_rebase_pipeline_wait_seconds
        new_pipeline, new_sha = await self._wait_for_post_rebase_pipeline(
            mr_iid, old_sha, timeout_seconds=timeout_seconds
        )

        if new_pipeline and new_pipeline.id != old_pipeline_id and new_pipeline.sha == new_sha:
            new_pipeline_url = await self.notifier.build_pipeline_url(new_pipeline.id)
            await sm.notify_pipeline_retry(
                old_pipeline_id=old_pipeline_id,
                old_pipeline_url=old_pipeline_url,
                new_pipeline_id=new_pipeline.id,
                new_pipeline_url=new_pipeline_url,
                retry_count=retry_count + 1,
                max_retries=max_retries,
                failed_jobs=failed_jobs,
                expected_sha=new_sha,
            )
            return True, datetime.now(UTC)

        # No auto-created pipeline - try to force-create one via API
        log.warning(
            "No auto-created pipeline after retry rebase, attempting force-create",
            mr_iid=mr_iid,
            old_pipeline_id=old_pipeline_id,
            old_sha=old_sha[:8],
            new_sha=new_sha[:8] if new_sha else "unknown",
        )

        # Get MR to fetch source_branch and current SHA
        mr = await self.gitlab_client.get_mr(mr_iid)
        source_branch = mr.source_branch
        current_sha = mr.sha

        try:
            created_pipeline = await self.gitlab_client.create_pipeline(source_branch)

            # Validate created pipeline has correct SHA (race condition protection)
            if created_pipeline.sha != current_sha:
                log.error(
                    "Force-created pipeline has wrong SHA (race condition)",
                    mr_iid=mr_iid,
                    pipeline_id=created_pipeline.id,
                    expected_sha=current_sha[:8],
                    actual_sha=created_pipeline.sha[:8],
                )
                await sm.trigger_pipeline_failed(
                    failed_jobs=failed_jobs,
                    retry_count=retry_count + 1,
                    error_message="Force-created pipeline has wrong SHA (race condition)",
                )
                return False, None

            new_pipeline_url = await self.notifier.build_pipeline_url(created_pipeline.id)
            await sm.notify_pipeline_retry(
                old_pipeline_id=old_pipeline_id,
                old_pipeline_url=old_pipeline_url,
                new_pipeline_id=created_pipeline.id,
                new_pipeline_url=new_pipeline_url,
                retry_count=retry_count + 1,
                max_retries=max_retries,
                failed_jobs=failed_jobs,
                expected_sha=current_sha,
            )
            log.info(
                "Force-created pipeline after retry rebase",
                mr_iid=mr_iid,
                pipeline_id=created_pipeline.id,
                sha=current_sha[:8],
            )
            return True, datetime.now(UTC)

        except (GitLabAPIError, GitLabNotFoundError) as e:
            log.exception(
                "Failed to force-create pipeline",
                mr_iid=mr_iid,
                source_branch=source_branch,
                error=str(e),
            )
            await sm.trigger_pipeline_failed(
                failed_jobs=failed_jobs,
                retry_count=retry_count + 1,
                error_message=f"Failed to create pipeline: {e}",
            )
            return False, None

    async def _wait_for_pipeline(self, ctx: ProcessingContext) -> ProcessingResult:
        """Poll pipeline status until success/failure or timeout."""
        mr_iid = ctx.mr_iid
        sm = ctx.state_machine
        timeout = timedelta(seconds=self.settings.pipeline_timeout_seconds)
        start_time = datetime.now(UTC)
        retry_count = 0
        max_retries = self.settings.pipeline_retry_count

        rebase_handler = RebaseDuringTestingHandler(
            gitlab_client=self.gitlab_client,
            settings=self.settings,
        )
        rebase_handler.set_shutdown_event(self._shutdown_event)

        rebase_ctx = RebaseDuringTestingContext(
            max_attempts=self.settings.max_rebase_during_testing,
        )
        last_rebase_check = datetime.now(UTC)

        log.info("Waiting for pipeline", mr_iid=mr_iid, timeout_seconds=timeout.total_seconds())

        while True:
            # Check termination conditions
            result = await self._check_pipeline_termination_conditions(ctx, sm, timeout, start_time)
            if result is not None:
                return result

            pipeline = await self.gitlab_client.get_latest_mr_pipeline(mr_iid)
            if pipeline is None:
                log.warning("No pipeline found", mr_iid=mr_iid)
                await self._interruptible_sleep(self.settings.pipeline_poll_interval_seconds)
                continue

            rebase_ctx = replace(rebase_ctx, current_pipeline_id=pipeline.id)

            log.debug("Pipeline status", mr_iid=mr_iid, pipeline_id=pipeline.id, status=pipeline.status)

            # Check if rebase needed
            outcome = await self._maybe_rebase_during_testing(
                ctx, sm, rebase_handler, rebase_ctx, pipeline, retry_count, last_rebase_check
            )
            last_rebase_check = outcome.last_check
            if outcome.result is not None:
                return outcome.result
            if outcome.should_reset and outcome.context is not None:
                rebase_ctx = outcome.context
                start_time = datetime.now(UTC)
                # Skip current (old) pipeline - wait for new one after rebase
                await self._interruptible_sleep(self.settings.pipeline_poll_interval_seconds)
                continue
            if outcome.context is not None:
                rebase_ctx = outcome.context

            # Skip stale pipelines using pipeline_id/SHA validation (not time-based)
            if await self._should_skip_stale_pipeline(mr_iid, pipeline):
                await self._interruptible_sleep(self.settings.pipeline_poll_interval_seconds)
                continue

            # Handle pipeline status
            status_result = await self._handle_pipeline_status(ctx, sm, pipeline, retry_count, max_retries)
            if status_result is None:
                await self._interruptible_sleep(self.settings.pipeline_poll_interval_seconds)
                continue

            if isinstance(status_result, RetrySignal):
                retry_count = status_result.retry_count
                start_time = status_result.new_start_time
                continue

            return status_result

    async def _check_pipeline_termination_conditions(
        self,
        ctx: ProcessingContext,
        sm: MRStateMachine,
        timeout: timedelta,
        start_time: datetime,
    ) -> ProcessingResult | None:
        """Check if pipeline wait should terminate early."""
        mr_iid = ctx.mr_iid

        if self._shutdown_event.is_set():
            log.info("Shutdown requested during pipeline wait", mr_iid=mr_iid)
            return ProcessingResult.ERROR

        elapsed = datetime.now(UTC) - start_time
        if elapsed > timeout:
            log.warning("Pipeline timeout", mr_iid=mr_iid, elapsed_seconds=elapsed.total_seconds())
            hours = max(1, int(timeout.total_seconds() / 3600))
            await sm.trigger_timeout(max_wait_hours=hours)
            return ProcessingResult.TIMEOUT

        if not await self._verify_mr_in_queue(mr_iid):
            await sm.trigger_mark_removed(reason="label_removed")
            return ProcessingResult.REMOVED

        return None

    async def _should_skip_stale_pipeline(self, mr_iid: int, pipeline: Pipeline) -> bool:
        """Check if pipeline should be skipped as stale.

        Uses pipeline_id/SHA validation to detect old pipelines from before
        rebase/retry. This matches the approach in PipelineWebhookHandler.

        Args:
            mr_iid: MR IID to check.
            pipeline: Current pipeline from GitLab API.

        Returns:
            True if pipeline should be skipped, False otherwise.
        """
        queue_item = await self.queue_manager.get_queue_item(mr_iid)
        if queue_item is None:
            return False

        # Skip if pipeline_id doesn't match (old pipeline from before rebase/retry)
        if queue_item.pipeline_id is not None and queue_item.pipeline_id != pipeline.id:
            log.debug(
                "Skipping old pipeline (pipeline_id mismatch)",
                mr_iid=mr_iid,
                current_pipeline_id=pipeline.id,
                expected_pipeline_id=queue_item.pipeline_id,
            )
            return True

        # Skip if SHA doesn't match (pipeline for wrong commit after rebase)
        if queue_item.expected_sha is not None and pipeline.sha != queue_item.expected_sha:
            log.debug(
                "Skipping pipeline with wrong SHA",
                mr_iid=mr_iid,
                pipeline_id=pipeline.id,
                pipeline_sha=pipeline.sha[:8] if pipeline.sha else "unknown",
                expected_sha=queue_item.expected_sha[:8],
            )
            return True

        return False

    async def _maybe_rebase_during_testing(
        self,
        ctx: ProcessingContext,
        sm: MRStateMachine,
        rebase_handler: RebaseDuringTestingHandler,
        rebase_ctx: RebaseDuringTestingContext,
        pipeline: Pipeline,
        retry_count: int,
        last_rebase_check: datetime,
    ) -> RebaseCheckOutcome:
        """Check and handle rebase during testing if interval elapsed.

        Returns:
            RebaseCheckOutcome with either updated context or error result.
        """
        now = datetime.now(UTC)
        check_interval = self.settings.rebase_check_interval_seconds

        if (now - last_rebase_check).total_seconds() < check_interval:
            return RebaseCheckOutcome(context=rebase_ctx, result=None, last_check=last_rebase_check, should_reset=False)

        rebase_result = await self._check_and_handle_rebase_during_testing(
            ctx, sm, rebase_handler, rebase_ctx, pipeline, retry_count
        )

        if rebase_result is None:
            return RebaseCheckOutcome(context=rebase_ctx, result=None, last_check=now, should_reset=False)

        if isinstance(rebase_result, RebaseDuringTestingContext):
            # Only reset start_time if we got a new pipeline (current_pipeline_id changed to a valid value)
            # If rebase happened but pipeline wait timed out, preserve the timing
            got_new_pipeline = (
                rebase_result.current_pipeline_id is not None
                and rebase_result.current_pipeline_id != rebase_ctx.current_pipeline_id
            )
            return RebaseCheckOutcome(context=rebase_result, result=None, last_check=now, should_reset=got_new_pipeline)

        return RebaseCheckOutcome(context=None, result=rebase_result, last_check=now, should_reset=False)

    async def _handle_pipeline_status(
        self,
        ctx: ProcessingContext,
        sm: MRStateMachine,
        pipeline: Pipeline,
        retry_count: int,
        max_retries: int,
    ) -> ProcessingResult | RetrySignal | None:
        """Handle pipeline status and return result or continue signal.

        Returns:
            - ProcessingResult: Final result, return from caller
            - RetrySignal: Retry with new count and start time, continue loop
            - None: No action needed, continue polling
        """
        mr_iid = ctx.mr_iid

        if pipeline.status == "success":
            # Validate SHA before processing success to prevent acting on stale pipeline
            queue_item = await self.queue_manager.get_queue_item(mr_iid)
            if queue_item and queue_item.expected_sha and pipeline.sha != queue_item.expected_sha:
                log.warning(
                    "Pipeline success but SHA mismatch - waiting for correct pipeline",
                    mr_iid=mr_iid,
                    pipeline_id=pipeline.id,
                    pipeline_sha=pipeline.sha[:8] if pipeline.sha else "unknown",
                    expected_sha=queue_item.expected_sha[:8],
                )
                return None  # Continue polling

            log.info("Pipeline succeeded", mr_iid=mr_iid, pipeline_id=pipeline.id)
            await sm.trigger_pipeline_success()
            return ProcessingResult.SUCCESS

        if pipeline.status in ("failed", "canceled"):
            return await self._handle_pipeline_failure(ctx, pipeline, retry_count, max_retries)

        non_actionable_statuses = ("skipped", "manual", "waiting_for_resource", "blocked")
        if pipeline.status in non_actionable_statuses:
            log.warning(
                "Pipeline in non-actionable state",
                mr_iid=mr_iid,
                pipeline_id=pipeline.id,
                status=pipeline.status,
            )
            await sm.trigger_pipeline_failed(
                failed_jobs=[],
                retry_count=retry_count,
                error_message=f"Pipeline status is '{pipeline.status}' - requires manual intervention",
            )
            return ProcessingResult.PIPELINE_FAILED

        return None

    async def _handle_pipeline_failure(
        self,
        ctx: ProcessingContext,
        pipeline: Pipeline,
        retry_count: int,
        max_retries: int,
    ) -> ProcessingResult | RetrySignal:
        """Handle failed/canceled pipeline status."""
        mr_iid = ctx.mr_iid
        failed_jobs = await self._get_failed_jobs(pipeline.id)

        # Sync retry_count with DB to prevent race with webhook handler
        queue_item = await self.queue_manager.get_queue_item(mr_iid)
        if queue_item and queue_item.retry_count is not None:
            retry_count = max(retry_count, queue_item.retry_count)

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
            return RetrySignal(retry_count=retry_count + 1, new_start_time=new_start)

        return ProcessingResult.PIPELINE_FAILED

    async def _check_and_handle_rebase_during_testing(
        self,
        ctx: ProcessingContext,
        sm: MRStateMachine,
        rebase_handler: RebaseDuringTestingHandler,
        rebase_ctx: RebaseDuringTestingContext,
        pipeline: Pipeline,
        retry_count: int,
    ) -> ProcessingResult | RebaseDuringTestingContext | None:
        """Check if rebase is needed during testing and handle it.

        Returns:
            - RebaseDuringTestingContext if rebase happened (continue polling)
            - ProcessingResult if error occurred (return from _wait_for_pipeline)
            - None if no rebase needed (continue polling)
        """
        mr_iid = ctx.mr_iid

        try:
            new_ctx, new_pipeline = await rebase_handler.handle_rebase_if_needed(
                mr_iid=mr_iid,
                ctx=rebase_ctx,
            )

            if new_pipeline:
                # Rebase happened, notify and continue
                await sm.notify_rebase_during_testing(
                    old_pipeline_id=pipeline.id,
                    new_pipeline_id=new_pipeline.id,
                    rebase_count=new_ctx.rebase_count,
                    max_attempts=new_ctx.max_attempts,
                )
                return new_ctx

            # Context may have been updated even without new pipeline (e.g., timeout waiting for pipeline)
            # Preserve the updated state for max_attempts tracking
            if new_ctx.rebase_count > rebase_ctx.rebase_count:
                log.debug(
                    "Rebase context updated but no new pipeline",
                    mr_iid=mr_iid,
                    rebase_count=new_ctx.rebase_count,
                )
                return new_ctx

            return None

        except RebaseRetryLimitExceeded as e:
            log.warning("Rebase retry limit exceeded", mr_iid=mr_iid, error=str(e))
            await sm.trigger_pipeline_failed(
                failed_jobs=[],
                retry_count=retry_count,
                error_message=str(e),
            )
            return ProcessingResult.PIPELINE_FAILED

        except GitLabConflictError as e:
            log.warning("Rebase conflict during testing", mr_iid=mr_iid)
            conflicted_files = await self.gitlab_client.get_mr_conflicts(mr_iid)
            await sm.trigger_conflict_during_testing(
                conflicted_files=conflicted_files,
                error_message=str(e),
            )
            return ProcessingResult.CONFLICT

        except GitLabAPIError as e:
            # Handle API errors from rebase wait, new pipeline wait, or API calls
            log.warning("GitLab API error during rebase in testing", mr_iid=mr_iid, error=str(e))
            await sm.trigger_pipeline_failed(
                failed_jobs=[],
                retry_count=retry_count,
                error_message=f"Rebase during testing failed: {e}",
            )
            return ProcessingResult.PIPELINE_FAILED

    async def _wait_for_rebase_quick(self, ctx: ProcessingContext) -> None:
        """Wait for rebase with a short timeout (for retry scenarios).

        Args:
            ctx: Processing context.

        Raises:
            GitLabAPIError: If rebase times out or fails.
            GitLabConflictError: If rebase has conflicts.
        """
        mr_iid = ctx.mr_iid

        # Exception holder for capturing errors from poll function.
        # poll_until_done doesn't propagate exceptions from poll_fn,
        # so we capture them here and raise after the poll completes.
        captured_error: Exception | None = None

        async def check_rebase() -> tuple[PollStatus, bool | None]:
            """Poll rebase status for quick retry scenario."""
            nonlocal captured_error
            rebase_in_progress, has_conflicts = await self.gitlab_client.check_rebase_status(mr_iid)

            if has_conflicts:
                conflicted_files = await self.gitlab_client.get_mr_conflicts(mr_iid)
                files_info = f": {conflicted_files}" if conflicted_files else ""
                captured_error = GitLabConflictError(f"Rebase conflict during retry{files_info}")
                return PollStatus.DONE, False

            if not rebase_in_progress:
                return PollStatus.DONE, True

            return PollStatus.CONTINUE, None

        config = PollingConfig(
            timeout_seconds=QUICK_REBASE_TIMEOUT_SECONDS,
            poll_interval_seconds=QUICK_REBASE_POLL_INTERVAL_SECONDS,
            operation_name="quick_rebase",
        )
        outcome = await poll_until_done(config, check_rebase, self._shutdown_event)

        # Check for captured exception
        if captured_error is not None:
            raise captured_error

        if outcome.completed and outcome.result:
            return

        if outcome.shutdown_requested:
            raise GitLabAPIError("Shutdown requested during quick rebase")

        if outcome.timed_out:
            raise GitLabAPIError("Rebase timeout during retry")

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

        # Get expected SHA from queue item for race condition detection
        queue_item = await self.queue_manager.get_queue_item(mr_iid)
        expected_sha = queue_item.expected_sha if queue_item else None

        log.info("Executing merge", mr_iid=mr_iid, expected_sha=expected_sha[:8] if expected_sha else None)

        try:
            # Add timeout for merge operation to prevent hanging
            merged_mr = await asyncio.wait_for(
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

    async def _capture_pre_rebase_sha(self, ctx: ProcessingContext) -> str:
        """Capture SHA before rebase for race condition prevention.

        Stores the SHA in the processing context and returns it.
        This is used to detect stale pipeline data after rebase.

        Args:
            ctx: Processing context to store SHA in.

        Returns:
            The captured SHA.
        """
        mr = await self.gitlab_client.get_mr(ctx.mr_iid)
        old_sha = mr.sha
        ctx.rebase_ctx.old_sha = old_sha
        log.debug("Captured pre-rebase SHA", mr_iid=ctx.mr_iid, old_sha=old_sha[:8])
        return old_sha

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

            if self.settings.queue_label not in mr.labels and self.settings.hotfix_label not in mr.labels:
                log.info("MR no longer has queue or hotfix label", mr_iid=mr_iid)
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
    "ProcessingContext",
    "ProcessingResult",
    "create_processor",
]
