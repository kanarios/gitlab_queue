"""Pipeline monitoring and job retry logic for the merge queue.

Extracted from MergeProcessor to reduce coupling (CBO).
Handles pipeline status polling, job-level retry,
and delegates rebase-during-testing to rebase_coordinator.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from gitlab_queue.clients.gitlab import GitLabAPIError
from gitlab_queue.core.handler_utils import interruptible_sleep, verify_mr_in_queue
from gitlab_queue.core.rebase_coordinator import (
    PipelineWaitState,
    create_pipeline_wait_state,
    maybe_rebase_during_testing,
)
from gitlab_queue.core.types import ProcessingContext, ProcessingResult, RebaseCheckOutcome, RetrySignal
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.core.notifier import MRNotifier
    from gitlab_queue.core.protocols import StateMachineProtocol
    from gitlab_queue.core.queue import QueueManager
    from gitlab_queue.models.pipeline import Job, Pipeline

log = get_logger(__name__)


@dataclass
class PipelineHandler:
    """Handles pipeline monitoring, status handling, and job-level retry.

    Manages the pipeline wait loop, detects failures, retries individual
    jobs, and coordinates rebase-during-testing.
    """

    gitlab_client: GitLabClient
    queue_manager: QueueManager
    notifier: MRNotifier
    settings: Settings
    shutdown_event: asyncio.Event
    rebase_check_fn: Callable[..., Awaitable[RebaseCheckOutcome]] | None = field(default=None)
    sleep_fn: Callable[[float], Awaitable[bool]] | None = field(default=None)

    def classify_failed_jobs(
        self,
        failed_jobs: list[Job],
        retried_jobs: dict[str, int],
        max_job_retries: int,
    ) -> tuple[list[Job], list[str]]:
        """Classify failed jobs into retryable and exhausted.

        Returns:
            Tuple of (jobs_to_retry, exhausted_job_names).
        """
        jobs_to_retry = []
        exhausted_jobs = []
        for job in failed_jobs:
            if retried_jobs.get(job.name, 0) < max_job_retries:
                jobs_to_retry.append(job)
            else:
                exhausted_jobs.append(job.name)
        return jobs_to_retry, exhausted_jobs

    async def dispatch_job_retries(
        self,
        ctx: ProcessingContext,
        pipeline: Pipeline,
        jobs_to_retry: list[Job],
        retried_jobs: dict[str, int],
        max_job_retries: int,
    ) -> tuple[bool, datetime | None, dict[str, int]]:
        """Execute parallel job retries via API and persist results to DB.

        Returns:
            Tuple of (should_continue, new_start_time, updated_retried_jobs).
        """
        results = await asyncio.gather(
            *[self.gitlab_client.retry_pipeline_job(j.id) for j in jobs_to_retry],
            return_exceptions=True,
        )

        updated, succeeded_job_names, failed_jobs_with_errors = self._tally_retry_results(
            results, jobs_to_retry, retried_jobs
        )

        if failed_jobs_with_errors:
            return await self._handle_retry_api_failures(
                ctx, pipeline, updated, succeeded_job_names, failed_jobs_with_errors, results
            )

        retried_job_names = list(dict.fromkeys(j.name for j in jobs_to_retry))

        await self.queue_manager.update_mr_state(
            ctx.mr_iid,
            "testing",
            retried_jobs=updated,
        )

        pipeline_url = await self.notifier.build_pipeline_url(pipeline.id)
        await ctx.state_machine.notify_job_retry(
            pipeline_id=pipeline.id,
            pipeline_url=pipeline_url,
            retried_jobs=retried_job_names,
            retried_counts=updated,
            max_retries=max_job_retries,
        )

        return True, datetime.now(UTC), updated

    @staticmethod
    def _tally_retry_results(
        results: Sequence[BaseException | object],
        jobs_to_retry: list[Job],
        retried_jobs: dict[str, int],
    ) -> tuple[dict[str, int], list[str], list[Job]]:
        """Count successes/failures from parallel retry results.

        Returns:
            Tuple of (updated_retried_jobs, succeeded_job_names, failed_jobs).
        """
        updated = dict(retried_jobs)
        seen: set[str] = set()
        succeeded_job_names: list[str] = []
        for i, r in enumerate(results):
            if not isinstance(r, BaseException):
                name = jobs_to_retry[i].name
                if name not in seen:
                    seen.add(name)
                    succeeded_job_names.append(name)
                    updated[name] = updated.get(name, 0) + 1

        failed_jobs = [jobs_to_retry[i] for i, r in enumerate(results) if isinstance(r, BaseException)]
        return updated, succeeded_job_names, failed_jobs

    async def _handle_retry_api_failures(
        self,
        ctx: ProcessingContext,
        pipeline: Pipeline,
        updated: dict[str, int],
        succeeded_job_names: list[str],
        failed_jobs_with_errors: list[Job],
        results: Sequence[BaseException | object],
    ) -> tuple[bool, datetime | None, dict[str, int]]:
        """Handle the case when some job retries failed via API.

        Returns:
            Tuple of (should_continue, new_start_time, updated_retried_jobs).
        """
        mr_iid = ctx.mr_iid
        first_error = next(r for r in results if isinstance(r, BaseException))
        log.warning("Failed to retry pipeline jobs", mr_iid=mr_iid, error=str(first_error))

        # Check if ALL failed retries are 403 "not retryable" — someone may have
        # already retried these jobs externally (e.g. via GitLab UI)
        all_not_retryable = all(
            isinstance(r, GitLabAPIError) and r.status_code == 403 for r in results if isinstance(r, BaseException)
        )

        if all_not_retryable:
            not_retryable_names = {j.name for j in failed_jobs_with_errors}
            all_jobs = await self.gitlab_client.get_pipeline_jobs(pipeline.id)
            active_statuses = ("running", "pending", "created")
            already_retried = [j for j in all_jobs if j.name in not_retryable_names and j.status in active_statuses]
            if already_retried:
                log.info(
                    "Jobs already retried externally, continuing poll",
                    mr_iid=mr_iid,
                    jobs=[j.name for j in already_retried],
                )
                return True, datetime.now(UTC), updated

        # Persist partial progress so successfully retried jobs are not retried again
        if succeeded_job_names:
            await self.queue_manager.update_mr_state(
                mr_iid,
                "testing",
                retried_jobs=updated,
            )

        await ctx.state_machine.trigger_pipeline_failed(
            failed_jobs=[j.name for j in failed_jobs_with_errors],
            retried_jobs=updated,
            error_message=f"Failed to retry jobs via API: {first_error}",
        )
        return False, None, updated

    async def _fetch_pipeline_jobs(
        self,
        mr_iid: int,
        sm: StateMachineProtocol,
        pipeline: Pipeline,
        retried_jobs: dict[str, int],
    ) -> list[Job] | None:
        """Fetch pipeline jobs from API, handling errors.

        Returns:
            List of jobs, or None if fetch failed (trigger_pipeline_failed already called).
        """
        try:
            all_jobs = await self.gitlab_client.get_pipeline_jobs(pipeline.id)
        except GitLabAPIError as e:
            log.exception("Failed to fetch pipeline jobs for retry", mr_iid=mr_iid, error=str(e))
            await sm.trigger_pipeline_failed(
                failed_jobs=[],
                retried_jobs=retried_jobs,
                error_message=f"Failed to fetch jobs: {e}",
            )
            return None
        except Exception as e:
            log.exception("Unexpected error fetching pipeline jobs", mr_iid=mr_iid, error=str(e))
            await sm.trigger_pipeline_failed(
                failed_jobs=[],
                retried_jobs=retried_jobs,
                error_message=f"Unexpected error fetching jobs: {e}",
            )
            return None

        if not all_jobs:
            log.warning(
                "Pipeline failed but no jobs returned from API",
                mr_iid=mr_iid,
                pipeline_id=pipeline.id,
            )
            await sm.trigger_pipeline_failed(
                failed_jobs=[],
                retried_jobs=retried_jobs,
                error_message="Pipeline failed but no jobs found (possible API issue)",
            )
            return None

        return all_jobs

    async def _handle_no_failed_jobs(
        self,
        mr_iid: int,
        sm: StateMachineProtocol,
        pipeline: Pipeline,
        all_jobs: list[Job],
        retried_jobs: dict[str, int],
    ) -> tuple[bool, datetime | None, dict[str, int]]:
        """Handle case when pipeline failed but no jobs have 'failed' status.

        Returns:
            Tuple of (should_continue, new_start_time, updated_retried_jobs).
        """
        # Double retry protection: after retry_pipeline_job, GitLab transitions jobs
        # to "running" before transitioning the pipeline itself. If we poll in this
        # window, we see pipeline="failed" + jobs="running". Continue polling.
        active_statuses = ("running", "pending", "created")
        active_jobs = [j for j in all_jobs if j.status in active_statuses]
        if active_jobs:
            log.info(
                "No failed jobs but jobs are actively running - race condition, continuing",
                mr_iid=mr_iid,
                pipeline_id=pipeline.id,
                active_jobs=[j.name for j in active_jobs],
            )
            return True, None, retried_jobs

        canceled_jobs = [j for j in all_jobs if j.status == "canceled"]
        if canceled_jobs:
            canceled_names = [j.name for j in canceled_jobs]
            log.warning(
                "Pipeline failed with canceled jobs",
                mr_iid=mr_iid,
                pipeline_id=pipeline.id,
                canceled_jobs=canceled_names,
            )
            await sm.trigger_pipeline_failed(
                failed_jobs=[],
                retried_jobs=retried_jobs,
                error_message=f"Pipeline failed: {len(canceled_jobs)} canceled job(s) found: {canceled_names}",
            )
            return False, None, retried_jobs

        log.warning(
            "Pipeline failed but no jobs in 'failed' status found",
            mr_iid=mr_iid,
            pipeline_id=pipeline.id,
            statuses=[j.status for j in all_jobs],
        )
        await sm.trigger_pipeline_failed(
            failed_jobs=[],
            retried_jobs=retried_jobs,
            error_message="Pipeline failed but no retryable jobs found",
        )
        return False, None, retried_jobs

    async def handle_pipeline_failure_retry(
        self,
        ctx: ProcessingContext,
        pipeline: Pipeline,
        retried_jobs: dict[str, int],
    ) -> tuple[bool, datetime | None, dict[str, int]]:
        """Retry individual failed jobs instead of rebasing.

        Returns:
            Tuple of (should_continue, new_start_time, updated_retried_jobs).
        """
        mr_iid = ctx.mr_iid
        sm = ctx.state_machine
        max_job_retries = self.settings.job_retry_count

        all_jobs = await self._fetch_pipeline_jobs(mr_iid, sm, pipeline, retried_jobs)
        if all_jobs is None:
            return False, None, retried_jobs

        failed_jobs = [j for j in all_jobs if j.status == "failed"]

        if not failed_jobs:
            return await self._handle_no_failed_jobs(mr_iid, sm, pipeline, all_jobs, retried_jobs)

        jobs_to_retry, exhausted_jobs = self.classify_failed_jobs(failed_jobs, retried_jobs, max_job_retries)

        if exhausted_jobs:
            await sm.trigger_pipeline_failed(
                failed_jobs=exhausted_jobs,
                retried_jobs=retried_jobs,
                error_message=f"Jobs failed after {max_job_retries} retry attempt(s): {exhausted_jobs}",
            )
            return False, None, retried_jobs

        return await self.dispatch_job_retries(ctx, pipeline, jobs_to_retry, retried_jobs, max_job_retries)

    async def wait_for_pipeline(self, ctx: ProcessingContext) -> ProcessingResult:
        """Poll pipeline status until success/failure or timeout."""
        state = await self._init_pipeline_wait_state(ctx)
        timeout = timedelta(seconds=self.settings.pipeline_timeout_seconds)

        log.info("Waiting for pipeline", mr_iid=ctx.mr_iid, timeout_seconds=timeout.total_seconds())

        while True:
            result = await self._process_pipeline_iteration(ctx, state, timeout)
            if result is not None:
                return result
            sleep = self.sleep_fn or self._interruptible_sleep
            await sleep(self.settings.pipeline_poll_interval_seconds)

    async def _init_pipeline_wait_state(self, ctx: ProcessingContext) -> PipelineWaitState:
        """Initialize mutable state for the pipeline wait loop."""
        queue_item = await self.queue_manager.get_queue_item(ctx.mr_iid)
        retried_jobs: dict[str, int] = queue_item.retried_jobs if queue_item else {}

        return create_pipeline_wait_state(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            shutdown_event=self.shutdown_event,
            retried_jobs=retried_jobs,
        )

    async def _process_pipeline_iteration(
        self,
        ctx: ProcessingContext,
        state: PipelineWaitState,
        timeout: timedelta,
    ) -> ProcessingResult | None:
        """Execute one iteration of the pipeline wait loop.

        Returns:
            ProcessingResult if loop should exit, None to continue.
        """
        mr_iid = ctx.mr_iid
        sm = ctx.state_machine

        # Check termination conditions
        result = await self.check_pipeline_termination_conditions(ctx, sm, timeout, state.start_time)
        if result is not None:
            return result

        pipeline = await self.gitlab_client.get_latest_mr_pipeline(mr_iid)
        if pipeline is None:
            log.warning("No pipeline found", mr_iid=mr_iid)
            return None

        state.rebase_ctx = replace(state.rebase_ctx, current_pipeline_id=pipeline.id)
        log.debug("Pipeline status", mr_iid=mr_iid, pipeline_id=pipeline.id, status=pipeline.status)

        # Check if rebase needed
        rebase_check = self.rebase_check_fn or maybe_rebase_during_testing
        outcome = await rebase_check(self.settings, ctx, state, pipeline)
        state.last_rebase_check = outcome.last_check
        rebase_result = await self._apply_rebase_outcome(state, mr_iid, outcome)
        if rebase_result is not None:
            return rebase_result

        # Skip stale pipelines
        if await self.should_skip_stale_pipeline(mr_iid, pipeline):
            return None

        # Grace period for transient canceled status (e.g. after retry_pipeline)
        if self._apply_canceled_grace_period(state, mr_iid, pipeline):
            return None

        # Handle pipeline status
        status_result = await self.handle_pipeline_status(ctx, sm, pipeline, state.retried_jobs)
        if status_result is None:
            return None

        if isinstance(status_result, RetrySignal):
            state.retried_jobs = status_result.retried_jobs
            if status_result.new_start_time is not None:
                state.start_time = status_result.new_start_time
            return None

        return status_result

    async def _apply_rebase_outcome(
        self,
        state: PipelineWaitState,
        mr_iid: int,
        outcome: RebaseCheckOutcome,
    ) -> ProcessingResult | None:
        """Apply rebase check outcome to pipeline wait state.

        Returns:
            ProcessingResult if loop should exit, None to continue.
        """
        if outcome.result is not None:
            return outcome.result
        if outcome.should_reset and outcome.context is not None:
            state.rebase_ctx = outcome.context
            await self.queue_manager.update_mr_state(mr_iid, "testing", retried_jobs={})
            state.retried_jobs = {}
            state.start_time = datetime.now(UTC)
            return None  # Skip current pipeline, wait for new one after rebase
        if outcome.context is not None:
            state.rebase_ctx = outcome.context
        return None

    @staticmethod
    def _apply_canceled_grace_period(
        state: PipelineWaitState,
        mr_iid: int,
        pipeline: Pipeline,
    ) -> bool:
        """Apply grace period for transient canceled/canceling status.

        Returns:
            True if current iteration should be skipped (grace period active).
        """
        if pipeline.status in ("canceled", "canceling"):
            state.canceled_seen_count += 1
            if state.canceled_seen_count <= 3:
                log.info(
                    "Pipeline canceled/canceling, grace poll",
                    mr_iid=mr_iid,
                    poll=state.canceled_seen_count,
                )
                return True
            return False
        state.canceled_seen_count = 0
        return False

    async def check_pipeline_termination_conditions(
        self,
        ctx: ProcessingContext,
        sm: StateMachineProtocol,
        timeout: timedelta,
        start_time: datetime,
    ) -> ProcessingResult | None:
        """Check if pipeline wait should terminate early."""
        mr_iid = ctx.mr_iid

        if self.shutdown_event.is_set():
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

    async def should_skip_stale_pipeline(self, mr_iid: int, pipeline: Pipeline) -> bool:
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
        # Note: with job-level retry, pipeline_id should NOT change (jobs are retried in-place).
        # If pipeline_id doesn't match during job retry, that's unexpected.
        if queue_item.pipeline_id is not None and queue_item.pipeline_id != pipeline.id:
            # If the new pipeline has the correct expected SHA and a higher ID,
            # it's a valid replacement (e.g., GitLab created a new pipeline after rebase).
            # Switch to tracking it instead of skipping.
            if (
                queue_item.expected_sha is not None
                and pipeline.sha is not None
                and pipeline.sha == queue_item.expected_sha
                and pipeline.id > queue_item.pipeline_id
            ):
                log.info(
                    "Switching to newer pipeline with matching SHA",
                    mr_iid=mr_iid,
                    old_pipeline_id=queue_item.pipeline_id,
                    new_pipeline_id=pipeline.id,
                    sha=pipeline.sha[:8],
                )
                await self.queue_manager.update_mr_state(
                    mr_iid,
                    "testing",
                    pipeline_id=pipeline.id,
                )
                return False

            log.debug(
                "Skipping old pipeline (pipeline_id mismatch)",
                mr_iid=mr_iid,
                current_pipeline_id=pipeline.id,
                expected_pipeline_id=queue_item.pipeline_id,
            )
            return True

        # Skip if SHA doesn't match (pipeline for wrong commit after rebase)
        if queue_item.expected_sha is not None and pipeline.sha is not None and pipeline.sha != queue_item.expected_sha:
            log.debug(
                "Skipping pipeline with wrong SHA",
                mr_iid=mr_iid,
                pipeline_id=pipeline.id,
                pipeline_sha=pipeline.sha[:8] if pipeline.sha else "unknown",
                expected_sha=queue_item.expected_sha[:8],
            )
            return True

        return False

    async def handle_pipeline_status(
        self,
        ctx: ProcessingContext,
        sm: StateMachineProtocol,
        pipeline: Pipeline,
        retried_jobs: dict[str, int],
    ) -> ProcessingResult | RetrySignal | None:
        """Handle pipeline status and return result or continue signal.

        Returns:
            - ProcessingResult: Final result, return from caller
            - RetrySignal: Retry with updated retried_jobs and start time, continue loop
            - None: No action needed, continue polling
        """
        mr_iid = ctx.mr_iid

        if pipeline.status == "success":
            # Validate SHA before processing success to prevent acting on stale pipeline
            queue_item = await self.queue_manager.get_queue_item(mr_iid)
            if (
                queue_item
                and queue_item.expected_sha
                and pipeline.sha is not None
                and pipeline.sha != queue_item.expected_sha
            ):
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

        if pipeline.status == "canceled":
            log.warning("Pipeline canceled, removing MR from queue", mr_iid=mr_iid)
            await sm.trigger_pipeline_failed(
                failed_jobs=[],
                retried_jobs=retried_jobs,
                error_message="Pipeline was canceled",
            )
            return ProcessingResult.PIPELINE_FAILED

        if pipeline.status == "failed":
            return await self.handle_pipeline_failure(ctx, pipeline, retried_jobs)

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
                retried_jobs=retried_jobs,
                error_message=f"Pipeline status is '{pipeline.status}' - requires manual intervention",
            )
            return ProcessingResult.PIPELINE_FAILED

        return None

    async def handle_pipeline_failure(
        self,
        ctx: ProcessingContext,
        pipeline: Pipeline,
        retried_jobs: dict[str, int],
    ) -> ProcessingResult | RetrySignal:
        """Handle failed pipeline status with job-level retry."""
        mr_iid = ctx.mr_iid
        retried_jobs = dict(retried_jobs)

        # Sync retried_jobs with DB (race condition protection, similar to old retry_count sync)
        queue_item = await self.queue_manager.get_queue_item(mr_iid)
        if queue_item and queue_item.retried_jobs:
            for job_name, count in queue_item.retried_jobs.items():
                retried_jobs[job_name] = max(retried_jobs.get(job_name, 0), count)

        log.warning(
            "Pipeline failed",
            mr_iid=mr_iid,
            pipeline_id=pipeline.id,
            retried_jobs=retried_jobs,
        )

        should_continue, new_start, updated_retried = await self.handle_pipeline_failure_retry(
            ctx, pipeline, retried_jobs
        )

        if should_continue:
            return RetrySignal(retried_jobs=updated_retried, new_start_time=new_start)

        return ProcessingResult.PIPELINE_FAILED

    async def _interruptible_sleep(self, seconds: float) -> bool:
        """Sleep that can be interrupted by shutdown event."""
        return await interruptible_sleep(self.shutdown_event, seconds)

    async def _verify_mr_in_queue(self, mr_iid: int) -> bool:
        """Verify MR still has queue label and is open."""
        return await verify_mr_in_queue(self.gitlab_client, self.settings, mr_iid)


__all__: list[str] = ["PipelineHandler"]
