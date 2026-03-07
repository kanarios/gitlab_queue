"""Rebase operations for the merge queue.

Extracted from MergeProcessor to reduce coupling (CBO).
Handles rebase initiation, polling, post-rebase pipeline waiting,
and quick rebase for retry scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from gitlab_queue.clients.gitlab import GitLabConflictError
from gitlab_queue.core.polling import PollingConfig, PollOutcome, PollStatus, poll_until_done
from gitlab_queue.core.types import ProcessingContext, ProcessingResult
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.core.notifier import MRNotifier
    from gitlab_queue.models.pipeline import Pipeline

log = get_logger(__name__)

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
        await self.capture_pre_rebase_sha(ctx)

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
                pipeline, new_sha = await self.wait_for_post_rebase_pipeline(
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
        outcome: PollOutcome[tuple[Pipeline | None, str]] = await self.poll_fn(
            config, check_pipeline, self.shutdown_event
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

    async def capture_pre_rebase_sha(self, ctx: ProcessingContext) -> str:
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
