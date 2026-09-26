"""Rebase operations for the merge queue.

Extracted from MergeProcessor to reduce coupling (CBO).
Handles rebase initiation, polling, post-rebase pipeline waiting,
and quick rebase for retry scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from gitlab_queue.clients.gitlab import GitLabAPIError, GitLabConflictError, GitLabServerError
from gitlab_queue.core.polling import PollingConfig, PollOutcome, PollStatus, poll_until_done
from gitlab_queue.core.types import ProcessingContext, ProcessingResult
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.core.notifier import MRNotifier
    from gitlab_queue.models.mr import MergeRequest
    from gitlab_queue.models.pipeline import Pipeline

log = get_logger(__name__)

# Polling intervals (seconds)
REBASE_POLL_INTERVAL_SECONDS = 5
QUICK_REBASE_POLL_INTERVAL_SECONDS = 3

# Timeouts (seconds)
QUICK_REBASE_TIMEOUT_SECONDS = 60
# Pipeline statuses the testing phase can follow to a result when reusing an
# existing pipeline. Anything else (failed, canceled, canceling, skipped,
# manual, blocked, ...) would fail the MR or stall it, so a new one is started.
REUSABLE_PIPELINE_STATUSES = frozenset(("success", "running", "pending", "created", "preparing"))


def _is_up_to_date(mr: MergeRequest) -> bool:
    """Check whether the MR already sits on top of the target branch.

    Only an explicit zero divergence counts: None means GitLab did not report
    it. GitLab also reports 0 when it cannot resolve a branch SHA, so the
    other signals must agree before skipping the rebase.
    """
    return (
        mr.diverged_commits_count == 0
        and bool(mr.sha)
        and not mr.has_conflicts
        and not mr.rebase_in_progress
        and mr.detailed_merge_status != "need_rebase"
    )


@dataclass
class RebaseHandler:
    """Handles rebase initiation, polling, and post-rebase pipeline waiting.

    Manages the full rebase lifecycle: initiating the rebase via GitLab API,
    polling for completion, and waiting for the new pipeline to start.
    """

    gitlab_client: GitLabClient
    notifier: MRNotifier
    settings: Settings
    shutdown_event: asyncio.Event
    poll_fn: Callable[..., Any] = field(default=poll_until_done)
    quick_rebase_timeout: int = QUICK_REBASE_TIMEOUT_SECONDS
    quick_rebase_poll_interval: int = QUICK_REBASE_POLL_INTERVAL_SECONDS

    async def process_rebase(self, ctx: ProcessingContext) -> ProcessingResult:
        """Initiate rebase and wait for completion.

        Skips the rebase entirely when the MR is already up-to-date with
        the target branch and moves on to testing with the current pipeline.
        Waits for a rebase that is already running (started from the GitLab
        UI, or by us before a restart) instead of starting another: GitLab
        rejects that with 409, which would look like a conflict.

        Args:
            ctx: Processing context.

        Returns:
            ProcessingResult.SUCCESS if rebase completed (or was not needed),
            or appropriate error result.
        """
        mr_iid = ctx.mr_iid
        sm = ctx.state_machine

        # Capture old SHA before rebase for race condition prevention
        mr, pipeline = await self.capture_pre_rebase_state(ctx)

        if _is_up_to_date(mr):
            log.info("Skipping rebase: MR is already up-to-date", mr_iid=mr_iid, sha=mr.sha[:8])
            return await self._start_testing_without_rebase(ctx, mr, pipeline)

        if mr.rebase_in_progress:
            log.info("Rebase already in progress, waiting for it", mr_iid=mr_iid)
            return await self.wait_for_rebase(ctx)

        log.info("Starting rebase", mr_iid=mr_iid, diverged_commits_count=mr.diverged_commits_count)

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
        return await self.wait_for_rebase(ctx)

    async def resume_rebase(self, ctx: ProcessingContext) -> ProcessingResult:
        """Continue an MR found in the rebasing state (e.g. after a restart).

        Whatever happened before the restart, the MR's current state decides:
        a finished rebase leaves it up-to-date and it goes straight to testing,
        a running one is waited for, and if none is running (never started,
        or the target moved on since) a new rebase is started. Just waiting
        for a SHA change there would time out and test an MR that is behind.

        Args:
            ctx: Processing context.

        Returns:
            ProcessingResult indicating outcome.
        """
        return await self.process_rebase(ctx)

    async def wait_for_rebase(self, ctx: ProcessingContext) -> ProcessingResult:
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
            rebase_in_progress, has_conflicts, merge_error = await self.gitlab_client.check_rebase_status(mr_iid)

            if has_conflicts:
                log.warning("Rebase has conflicts", mr_iid=mr_iid)
                conflicted_files = await self.gitlab_client.get_mr_conflicts(mr_iid)
                error_message = merge_error or "Rebase failed due to merge conflicts"
                await sm.trigger_rebase_failed(
                    conflicted_files=conflicted_files,
                    error_message=error_message,
                )
                return PollStatus.DONE, ProcessingResult.CONFLICT

            if not rebase_in_progress:
                log.info("Rebase completed", mr_iid=mr_iid)
                old_sha = ctx.rebase_ctx.old_sha
                pipeline, new_sha = await self.wait_for_post_rebase_pipeline(
                    mr_iid,
                    old_sha,
                    old_pipeline_id=ctx.rebase_ctx.old_pipeline_id,
                )

                if pipeline:
                    await self._enter_testing(ctx, pipeline, new_sha)
                    return PollStatus.DONE, ProcessingResult.SUCCESS

                if new_sha == old_sha and not self.shutdown_event.is_set():
                    # SHA never moved: the rebase was a no-op, so GitLab won't start a pipeline
                    log.info("Rebase did not change SHA, treating MR as up-to-date", mr_iid=mr_iid)
                    mr = await self.gitlab_client.get_mr(mr_iid)
                    current_pipeline = await self.gitlab_client.get_latest_mr_pipeline(mr_iid)
                    return PollStatus.DONE, await self._start_testing_without_rebase(ctx, mr, current_pipeline)

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
        outcome = await self.poll_fn(config, check_rebase, self.shutdown_event)

        if outcome.completed and outcome.result is not None:
            result: ProcessingResult = outcome.result
            return result

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

    async def wait_for_post_rebase_pipeline(
        self,
        mr_iid: int,
        old_sha: str,
        *,
        old_pipeline_id: int | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[Pipeline | None, str]:
        """Wait for a pipeline on the MR's new SHA after rebase.

        After a rebase GitLab may briefly keep reporting the old SHA and
        pipeline (API caching, pipeline not created yet), so this waits until
        the SHA changes and a pipeline on the new SHA shows up.

        Args:
            mr_iid: MR IID to wait for.
            old_sha: SHA before rebase started.
            old_pipeline_id: Pipeline ID before rebase (to detect stale responses).
            timeout_seconds: Maximum time to wait (default: post_rebase_pipeline_wait_seconds).

        Returns:
            Tuple of (pipeline, current_sha). pipeline is None on shutdown or
            when no pipeline on the new SHA appeared in time; current_sha
            equals old_sha if the SHA never changed.
        """

        async def check_pipeline() -> tuple[PollStatus, tuple[Pipeline | None, str] | None]:
            """Poll for new pipeline on updated SHA after rebase."""
            mr = await self.gitlab_client.get_mr(mr_iid)

            if mr.rebase_in_progress:
                return PollStatus.CONTINUE, None

            if mr.sha == old_sha:
                log.debug("SHA not updated after rebase yet", mr_iid=mr_iid, sha=old_sha[:8])
                return PollStatus.CONTINUE, None

            pipeline = await self.gitlab_client.get_latest_mr_pipeline(mr_iid)

            # Skip stale pipeline from before rebase (race condition)
            if pipeline and pipeline.id == old_pipeline_id:
                log.info(
                    "Skipping stale pipeline from before rebase",
                    mr_iid=mr_iid,
                    pipeline_id=pipeline.id,
                    old_pipeline_id=old_pipeline_id,
                )
                return PollStatus.CONTINUE, None

            if pipeline and pipeline.sha == mr.sha:
                log.info(
                    "Found pipeline with new SHA after rebase",
                    mr_iid=mr_iid,
                    pipeline_id=pipeline.id,
                    pipeline_status=pipeline.status,
                    old_sha=old_sha[:8],
                    new_sha=mr.sha[:8],
                )
                return PollStatus.DONE, (pipeline, mr.sha)

            return PollStatus.CONTINUE, None

        config = PollingConfig(
            timeout_seconds=timeout_seconds or self.settings.post_rebase_pipeline_wait_seconds,
            poll_interval_seconds=self.settings.pipeline_poll_interval_seconds,
            operation_name="post_rebase_pipeline",
        )
        outcome: PollOutcome[tuple[Pipeline | None, str]] = await self.poll_fn(
            config, check_pipeline, self.shutdown_event
        )

        if outcome.completed and outcome.result:
            return outcome.result

        if outcome.shutdown_requested:
            return None, old_sha

        # Timeout - return current state with SHA validation
        mr = await self.gitlab_client.get_mr(mr_iid)
        if mr.sha == old_sha:
            log.warning("Timeout waiting for SHA change after rebase", mr_iid=mr_iid, sha=old_sha[:8])
            return None, old_sha

        pipeline = await self.gitlab_client.get_latest_mr_pipeline(mr_iid)
        log.warning(
            "Timeout waiting for post-rebase pipeline",
            mr_iid=mr_iid,
            old_sha=old_sha[:8],
            current_sha=mr.sha[:8],
            pipeline_id=pipeline.id if pipeline else None,
            pipeline_sha=pipeline.sha[:8] if pipeline and pipeline.sha else None,
        )
        # Don't return stale pipeline if SHA doesn't match
        if pipeline and pipeline.sha == mr.sha:
            return pipeline, mr.sha
        return None, mr.sha

    async def _try_create_pipeline(
        self,
        source_branch: str,
        mr_iid: int,
        new_sha: str,
        *,
        fallback_pipeline_id: int | None = None,
    ) -> tuple[PollStatus, tuple[Pipeline, str] | None]:
        """Try to create a pipeline, returning CONTINUE on server error.

        On client error (4xx), falls back to retry_pipeline if fallback_pipeline_id
        is available. This handles the case where workflow:rules blocks source=api.
        """
        try:
            new_pipeline = await self.gitlab_client.create_pipeline(source_branch)
            return PollStatus.DONE, (new_pipeline, new_sha)
        except GitLabServerError as e:
            log.warning("create_pipeline failed (server error), will retry", mr_iid=mr_iid, error=str(e))
            return PollStatus.CONTINUE, None
        except GitLabAPIError as e:
            if fallback_pipeline_id is None:
                raise
            log.warning(
                "create_pipeline client error, falling back to retry_pipeline",
                mr_iid=mr_iid,
                fallback_pipeline_id=fallback_pipeline_id,
                error=str(e),
            )
            try:
                retried = await self.gitlab_client.retry_pipeline(fallback_pipeline_id)
                return PollStatus.DONE, (retried, new_sha)
            except GitLabServerError as retry_err:
                log.warning("retry_pipeline failed (server error), will retry", mr_iid=mr_iid, error=str(retry_err))
                return PollStatus.CONTINUE, None

    async def _enter_testing(self, ctx: ProcessingContext, pipeline: Pipeline, sha: str) -> None:
        """Hand the MR over to testing with the given pipeline and expected SHA."""
        pipeline_url = await self.notifier.build_pipeline_url(pipeline.id)
        await ctx.state_machine.trigger_rebase_complete(
            pipeline_id=pipeline.id,
            pipeline_url=pipeline_url,
            expected_sha=sha,
        )

    async def _resolve_current_pipeline(
        self,
        mr: MergeRequest,
        pipeline: Pipeline | None,
    ) -> tuple[PollStatus, tuple[Pipeline, str] | None]:
        """Pick the pipeline to test an MR whose SHA did not change.

        Reuses the latest pipeline if it runs on the MR's SHA and can still
        produce a result; otherwise starts a new one, because GitLab does not
        create a pipeline when nothing was pushed.
        """
        current = pipeline if pipeline and pipeline.sha == mr.sha else None
        if current and current.status in REUSABLE_PIPELINE_STATUSES:
            return PollStatus.DONE, (current, mr.sha)

        log.info(
            "Creating new pipeline: no usable pipeline for current SHA",
            mr_iid=mr.iid,
            pipeline_id=pipeline.id if pipeline else None,
            pipeline_status=pipeline.status if pipeline else None,
        )
        # Retrying an old pipeline only makes sense if it ran on the current SHA
        status, result = await self._try_create_pipeline(
            mr.source_branch,
            mr.iid,
            mr.sha,
            fallback_pipeline_id=current.id if current else None,
        )
        if result and result[0].sha != mr.sha:
            # Branch moved between reading the MR and creating the pipeline
            log.info(
                "Created pipeline is on a different SHA, re-reading MR",
                mr_iid=mr.iid,
                pipeline_id=result[0].id,
                pipeline_sha=result[0].sha[:8],
                expected_sha=mr.sha[:8],
            )
            return PollStatus.CONTINUE, None
        return status, result

    async def _start_testing_without_rebase(
        self,
        ctx: ProcessingContext,
        mr: MergeRequest,
        pipeline: Pipeline | None,
    ) -> ProcessingResult:
        """Move an up-to-date MR to testing without calling the rebase API.

        Tries the already-fetched MR state first; if pipeline creation hits a
        transient error, polls with fresh MR state until a pipeline is found.

        Raises:
            GitLabAPIError: If no pipeline could be started before the timeout.
        """
        mr_iid = ctx.mr_iid
        status, result = await self._resolve_current_pipeline(mr, pipeline)

        if status != PollStatus.DONE:

            async def check_pipeline() -> tuple[PollStatus, tuple[Pipeline, str] | None]:
                """Re-read MR state and resolve its pipeline."""
                current_mr = await self.gitlab_client.get_mr(mr_iid)
                current_pipeline = await self.gitlab_client.get_latest_mr_pipeline(mr_iid)
                return await self._resolve_current_pipeline(current_mr, current_pipeline)

            config = PollingConfig(
                timeout_seconds=self.settings.post_rebase_pipeline_wait_seconds,
                poll_interval_seconds=self.settings.pipeline_poll_interval_seconds,
                operation_name="reuse_pipeline",
            )
            outcome: PollOutcome[tuple[Pipeline, str]] = await self.poll_fn(config, check_pipeline, self.shutdown_event)
            if outcome.shutdown_requested:
                log.info("Shutdown requested while starting pipeline", mr_iid=mr_iid)
                return ProcessingResult.ERROR
            result = outcome.result if outcome.completed else None

        if not result:
            raise GitLabAPIError(f"Could not start pipeline for up-to-date MR !{mr_iid}")

        await self._enter_testing(ctx, *result)
        return ProcessingResult.SUCCESS

    async def capture_pre_rebase_state(self, ctx: ProcessingContext) -> tuple[MergeRequest, Pipeline | None]:
        """Capture SHA and pipeline ID before rebase for race condition prevention.

        Stores the SHA and current pipeline ID in the processing context;
        both are used to detect stale pipeline data after rebase. The MR is
        fetched with its divergence from target so callers can tell whether
        a rebase is needed at all.

        Args:
            ctx: Processing context to store SHA and pipeline ID in.

        Returns:
            The fetched MR and its latest pipeline (if any).
        """
        mr = await self.gitlab_client.get_mr(ctx.mr_iid, include_diverged_commits_count=True)
        ctx.rebase_ctx.old_sha = mr.sha

        pipeline = await self.gitlab_client.get_latest_mr_pipeline(ctx.mr_iid)
        ctx.rebase_ctx.old_pipeline_id = pipeline.id if pipeline else None

        log.debug(
            "Captured pre-rebase state",
            mr_iid=ctx.mr_iid,
            old_sha=mr.sha[:8],
            old_pipeline_id=ctx.rebase_ctx.old_pipeline_id,
            diverged_commits_count=mr.diverged_commits_count,
        )
        return mr, pipeline

    async def wait_for_rebase_quick(self, ctx: ProcessingContext) -> None:
        """Wait for rebase with a short timeout (for retry scenarios).

        Args:
            ctx: Processing context.

        Raises:
            GitLabAPIError: If rebase times out or fails.
            GitLabConflictError: If rebase has conflicts.
        """
        from gitlab_queue.core.handler_utils import wait_for_rebase_completion

        await wait_for_rebase_completion(
            self.gitlab_client,
            ctx.mr_iid,
            timeout_seconds=self.quick_rebase_timeout,
            poll_interval_seconds=self.quick_rebase_poll_interval,
            operation_name="quick_rebase",
            shutdown_event=self.shutdown_event,
            fetch_conflict_details=True,
            conflict_error_prefix="Rebase conflict during retry",
            timeout_error_message="Rebase timeout during retry",
            shutdown_error_message="Shutdown requested during quick rebase",
        )


__all__: list[str] = ["RebaseHandler"]
