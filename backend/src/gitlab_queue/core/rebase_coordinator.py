"""Rebase-during-testing coordination for the pipeline wait loop.

Extracted from PipelineHandler to reduce coupling (CBO).
Contains PipelineWaitState and free functions for rebase checks
during pipeline monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from gitlab_queue.clients.gitlab import GitLabAPIError, GitLabConflictError
from gitlab_queue.core.rebase_during_testing import (
    RebaseDuringTestingContext,
    RebaseDuringTestingHandler,
    RebaseRetryLimitExceeded,
)
from gitlab_queue.core.types import ProcessingContext, ProcessingResult, RebaseCheckOutcome
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    import asyncio

    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.models.pipeline import Pipeline

log = get_logger(__name__)


@dataclass
class PipelineWaitState:
    """Mutable state for the pipeline wait loop."""

    retried_jobs: dict[str, int]
    start_time: datetime
    rebase_ctx: RebaseDuringTestingContext
    last_rebase_check: datetime
    rebase_handler: RebaseDuringTestingHandler


def create_pipeline_wait_state(
    settings: Settings,
    gitlab_client: GitLabClient,
    shutdown_event: asyncio.Event,
    retried_jobs: dict[str, int],
) -> PipelineWaitState:
    """Create initial PipelineWaitState with a configured rebase handler."""
    rebase_handler = RebaseDuringTestingHandler(
        gitlab_client=gitlab_client,
        settings=settings,
    )
    rebase_handler.set_shutdown_event(shutdown_event)

    return PipelineWaitState(
        retried_jobs=retried_jobs,
        start_time=datetime.now(UTC),
        rebase_ctx=RebaseDuringTestingContext(
            max_attempts=settings.max_rebase_during_testing,
        ),
        last_rebase_check=datetime.now(UTC),
        rebase_handler=rebase_handler,
    )


async def maybe_rebase_during_testing(
    settings: Settings,
    ctx: ProcessingContext,
    state: PipelineWaitState,
    pipeline: Pipeline,
) -> RebaseCheckOutcome:
    """Check and handle rebase during testing if interval elapsed.

    Returns:
        RebaseCheckOutcome with either updated context or error result.
    """
    now = datetime.now(UTC)
    check_interval = settings.rebase_check_interval_seconds

    if (now - state.last_rebase_check).total_seconds() < check_interval:
        return RebaseCheckOutcome(
            context=state.rebase_ctx,
            result=None,
            last_check=state.last_rebase_check,
            should_reset=False,
        )

    rebase_result = await check_and_handle_rebase_during_testing(
        state.rebase_handler.gitlab_client, ctx, state, pipeline
    )

    if rebase_result is None:
        return RebaseCheckOutcome(context=state.rebase_ctx, result=None, last_check=now, should_reset=False)

    if isinstance(rebase_result, RebaseDuringTestingContext):
        got_new_pipeline = (
            rebase_result.current_pipeline_id is not None
            and rebase_result.current_pipeline_id != state.rebase_ctx.current_pipeline_id
        )
        return RebaseCheckOutcome(context=rebase_result, result=None, last_check=now, should_reset=got_new_pipeline)

    return RebaseCheckOutcome(context=None, result=rebase_result, last_check=now, should_reset=False)


async def check_and_handle_rebase_during_testing(
    gitlab_client: GitLabClient,
    ctx: ProcessingContext,
    state: PipelineWaitState,
    pipeline: Pipeline,
) -> ProcessingResult | RebaseDuringTestingContext | None:
    """Check if rebase is needed during testing and handle it.

    Returns:
        - RebaseDuringTestingContext if rebase happened (continue polling)
        - ProcessingResult if error occurred (return from _wait_for_pipeline)
        - None if no rebase needed (continue polling)
    """
    mr_iid = ctx.mr_iid
    sm = ctx.state_machine

    try:
        new_ctx, new_pipeline = await state.rebase_handler.handle_rebase_if_needed(
            mr_iid=mr_iid,
            ctx=state.rebase_ctx,
        )

        if new_pipeline:
            await sm.notify_rebase_during_testing(
                old_pipeline_id=pipeline.id,
                new_pipeline_id=new_pipeline.id,
                rebase_count=new_ctx.rebase_count,
                max_attempts=new_ctx.max_attempts,
            )
            return new_ctx

        if new_ctx.rebase_count > state.rebase_ctx.rebase_count:
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
            retried_jobs=state.retried_jobs,
            error_message=str(e),
        )
        return ProcessingResult.PIPELINE_FAILED

    except GitLabConflictError as e:
        log.warning("Rebase conflict during testing", mr_iid=mr_iid)
        conflicted_files = await gitlab_client.get_mr_conflicts(mr_iid)
        await sm.trigger_conflict_during_testing(
            conflicted_files=conflicted_files,
            error_message=str(e),
        )
        return ProcessingResult.CONFLICT

    except GitLabAPIError as e:
        log.warning("GitLab API error during rebase in testing", mr_iid=mr_iid, error=str(e))
        await sm.trigger_pipeline_failed(
            failed_jobs=[],
            retried_jobs=state.retried_jobs,
            error_message=f"Rebase during testing failed: {e}",
        )
        return ProcessingResult.PIPELINE_FAILED


__all__: list[str] = [
    "PipelineWaitState",
    "check_and_handle_rebase_during_testing",
    "create_pipeline_wait_state",
    "maybe_rebase_during_testing",
]
