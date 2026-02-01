"""Auto-rebase during testing when target branch changes.

Handles the case where another MR is merged while the current MR's pipeline
is running, requiring a rebase to maintain fast-forward merge compatibility.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from gitlab_queue.clients.gitlab import GitLabAPIError, GitLabConflictError
from gitlab_queue.core.polling import PollingConfig, PollStatus, poll_until_done
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.models.pipeline import Pipeline

log = get_logger(__name__)


# Polling interval for waiting for rebase completion and new pipeline
REBASE_POLL_INTERVAL_SECONDS = 3
PIPELINE_WAIT_POLL_SECONDS = 2


class MergeReadiness(Enum):
    """MR merge readiness status based on GitLab's merge_status field."""

    READY = "ready"
    NEEDS_REBASE = "needs_rebase"
    HAS_CONFLICTS = "has_conflicts"


@dataclass
class RebaseDuringTestingContext:
    """Tracks rebase attempts during testing phase."""

    rebase_count: int = 0
    max_attempts: int = 3
    current_pipeline_id: int | None = None


class RebaseRetryLimitExceeded(Exception):
    """Maximum rebase attempts during testing exceeded."""


@dataclass
class RebaseDuringTestingHandler:
    """Handles auto-rebase when target branch changes during testing.

    When an MR is in the testing state and another MR gets merged,
    the current MR may no longer be mergeable due to requiring a rebase.
    This handler detects this condition, cancels the current pipeline,
    performs a rebase, and waits for a new pipeline to start.
    """

    gitlab_client: GitLabClient
    settings: Settings
    _shutdown_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    def set_shutdown_event(self, event: asyncio.Event) -> None:
        """Set the shutdown event for interruptible operations."""
        self._shutdown_event = event

    async def check_needs_rebase(self, mr_iid: int) -> MergeReadiness:
        """Check if MR needs rebase based on merge_status.

        Args:
            mr_iid: MR internal ID to check.

        Returns:
            MergeReadiness indicating current state.
        """
        mr = await self.gitlab_client.get_mr(mr_iid)

        if mr.has_conflicts:
            return MergeReadiness.HAS_CONFLICTS

        # GitLab merge_status values that indicate MR is ready:
        # "can_be_merged" - ready to merge
        # "checking" - GitLab is still calculating (treat as ready for now)
        if mr.merge_status in ("can_be_merged", "checking"):
            return MergeReadiness.READY

        # Other statuses that require rebase:
        # "cannot_be_merged_recheck", "cannot_be_merged", "unchecked"
        return MergeReadiness.NEEDS_REBASE

    async def handle_rebase_if_needed(
        self,
        mr_iid: int,
        ctx: RebaseDuringTestingContext,
    ) -> tuple[RebaseDuringTestingContext, Pipeline | None]:
        """Cancel pipeline, rebase, and wait for new pipeline if needed.

        Args:
            mr_iid: MR internal ID to handle.
            ctx: Current rebase context tracking attempts.

        Returns:
            Tuple of (updated_context, new_pipeline).
            new_pipeline is None if no rebase was needed.

        Raises:
            RebaseRetryLimitExceeded: If max attempts reached.
            GitLabConflictError: If rebase has conflicts.
        """
        readiness = await self.check_needs_rebase(mr_iid)

        if readiness == MergeReadiness.READY:
            return ctx, None

        if readiness == MergeReadiness.HAS_CONFLICTS:
            raise GitLabConflictError("MR has conflicts during testing")

        # NEEDS_REBASE case
        if ctx.rebase_count >= ctx.max_attempts:
            raise RebaseRetryLimitExceeded(
                f"MR !{mr_iid}: {ctx.rebase_count}/{ctx.max_attempts} rebase attempts exhausted"
            )

        log.info(
            "Rebase needed during testing",
            mr_iid=mr_iid,
            rebase_count=ctx.rebase_count + 1,
            max_attempts=ctx.max_attempts,
        )

        # 1. Cancel current pipeline if running
        if ctx.current_pipeline_id:
            await self._cancel_pipeline_safe(ctx.current_pipeline_id)

        # 2. Capture old SHA for new pipeline detection
        mr = await self.gitlab_client.get_mr(mr_iid)
        old_sha = mr.sha

        # 3. Initiate rebase
        try:
            await self.gitlab_client.rebase_mr(mr_iid)
        except GitLabConflictError:
            log.warning("Rebase conflict during testing", mr_iid=mr_iid)
            raise

        # 4. Wait for rebase completion
        await self._wait_for_rebase(mr_iid)

        # 5. Wait for new pipeline with correct SHA
        new_pipeline = await self._wait_for_new_pipeline(mr_iid, old_sha)

        # 6. Return updated context
        new_ctx = RebaseDuringTestingContext(
            rebase_count=ctx.rebase_count + 1,
            max_attempts=ctx.max_attempts,
            current_pipeline_id=new_pipeline.id if new_pipeline else None,
        )

        log.info(
            "Rebase during testing completed",
            mr_iid=mr_iid,
            new_pipeline_id=new_pipeline.id if new_pipeline else None,
            rebase_count=new_ctx.rebase_count,
        )

        return new_ctx, new_pipeline

    async def _cancel_pipeline_safe(self, pipeline_id: int) -> None:
        """Cancel pipeline, ignoring errors if already finished.

        Args:
            pipeline_id: Pipeline ID to cancel.
        """
        try:
            await self.gitlab_client.cancel_pipeline(pipeline_id)
            log.info("Pipeline cancelled for rebase", pipeline_id=pipeline_id)
        except GitLabAPIError as e:
            # Pipeline may already be finished or cancelled
            log.debug(
                "Could not cancel pipeline (may be finished)",
                pipeline_id=pipeline_id,
                error=str(e),
            )

    async def _wait_for_rebase(self, mr_iid: int) -> None:
        """Wait for rebase operation to complete.

        Args:
            mr_iid: MR internal ID.

        Raises:
            GitLabConflictError: If rebase results in conflicts.
            GitLabAPIError: If rebase times out or shutdown requested.
        """
        # Exception holder for capturing errors from poll function.
        # poll_until_done doesn't propagate exceptions from poll_fn,
        # so we capture them here and raise after the poll completes.
        captured_error: Exception | None = None

        async def check_rebase() -> tuple[PollStatus, bool | None]:
            """Poll rebase status until complete or conflict detected."""
            nonlocal captured_error
            rebase_in_progress, has_conflicts = await self.gitlab_client.check_rebase_status(mr_iid)

            if has_conflicts:
                captured_error = GitLabConflictError("Rebase conflict during testing")
                return PollStatus.DONE, False

            if not rebase_in_progress:
                return PollStatus.DONE, True

            return PollStatus.CONTINUE, None

        config = PollingConfig(
            timeout_seconds=self.settings.rebase_timeout_seconds,
            poll_interval_seconds=REBASE_POLL_INTERVAL_SECONDS,
            operation_name="rebase_during_testing",
        )
        outcome = await poll_until_done(config, check_rebase, self._shutdown_event)

        # Check for captured exception
        if captured_error is not None:
            raise captured_error

        if outcome.completed and outcome.result:
            return

        if outcome.shutdown_requested:
            raise GitLabAPIError("Shutdown requested during rebase wait")

        if outcome.timed_out:
            raise GitLabAPIError(f"Rebase timeout after {self.settings.rebase_timeout_seconds}s")

    async def _wait_for_new_pipeline(
        self,
        mr_iid: int,
        old_sha: str,
    ) -> Pipeline | None:
        """Wait for a new pipeline after rebase.

        Args:
            mr_iid: MR internal ID.
            old_sha: SHA before rebase to detect new pipeline.

        Returns:
            New Pipeline if found, None if timeout.
        """

        async def check_pipeline() -> tuple[PollStatus, Pipeline | None]:
            """Poll for new pipeline on updated SHA after rebase."""
            mr = await self.gitlab_client.get_mr(mr_iid)
            new_sha = mr.sha

            # Check if SHA changed (rebase created new commit) or rebase completed
            # without changing SHA (no-op rebase). Using "is False" to distinguish
            # from None/unknown state.
            # Note: Fast-forward scenario (SHA unchanged) is handled by line 261
            # which validates pipeline.sha == new_sha before returning.
            if new_sha != old_sha or mr.rebase_in_progress is False:
                pipeline = await self.gitlab_client.get_latest_mr_pipeline(mr_iid)
                # Skip cancelled/failed pipelines from before
                if pipeline and pipeline.sha == new_sha and pipeline.status not in ("canceled", "failed"):
                    return PollStatus.DONE, pipeline

            return PollStatus.CONTINUE, None

        config = PollingConfig(
            timeout_seconds=self.settings.post_rebase_pipeline_wait_seconds,
            poll_interval_seconds=PIPELINE_WAIT_POLL_SECONDS,
            operation_name="new_pipeline_after_rebase",
        )
        outcome = await poll_until_done(config, check_pipeline, self._shutdown_event)

        if outcome.completed and outcome.result:
            return outcome.result

        if outcome.shutdown_requested:
            return None

        # Timeout - try to get current pipeline with validation
        log.warning(
            "Timeout waiting for new pipeline after rebase",
            mr_iid=mr_iid,
            old_sha=old_sha[:8],
        )
        mr = await self.gitlab_client.get_mr(mr_iid)
        pipeline = await self.gitlab_client.get_latest_mr_pipeline(mr_iid)
        if pipeline and pipeline.sha == mr.sha and pipeline.status not in ("canceled", "failed"):
            return pipeline
        log.warning(
            "No valid pipeline found after rebase timeout",
            mr_iid=mr_iid,
            pipeline_id=pipeline.id if pipeline else None,
            pipeline_sha=pipeline.sha[:8] if pipeline else None,
            mr_sha=mr.sha[:8],
            pipeline_status=pipeline.status if pipeline else None,
        )
        return None


__all__: list[str] = [
    "MergeReadiness",
    "RebaseDuringTestingContext",
    "RebaseDuringTestingHandler",
    "RebaseRetryLimitExceeded",
]
