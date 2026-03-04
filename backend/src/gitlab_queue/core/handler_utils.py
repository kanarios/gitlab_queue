"""Shared utility functions for processor and handler classes.

Eliminates duplication of interruptible_sleep and verify_mr_in_queue
between MergeProcessor and PipelineHandler.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from gitlab_queue.clients.gitlab import GitLabAPIError, GitLabConflictError, GitLabNotFoundError
from gitlab_queue.core.polling import PollingConfig, PollStatus, poll_until_done
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings

log = get_logger(__name__)


async def interruptible_sleep(shutdown_event: asyncio.Event, seconds: float) -> bool:
    """Sleep that can be interrupted by shutdown event.

    Args:
        shutdown_event: Event to monitor for shutdown.
        seconds: Number of seconds to sleep.

    Returns:
        True if sleep completed, False if interrupted by shutdown.
    """
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=seconds)
        return False
    except TimeoutError:
        return True


async def verify_mr_in_queue(
    gitlab_client: GitLabClient,
    settings: Settings,
    mr_iid: int,
) -> bool:
    """Verify MR still has queue label and is open.

    Args:
        gitlab_client: GitLab API client.
        settings: Application settings.
        mr_iid: MR IID to verify.

    Returns:
        True if MR is still valid for processing.
    """
    try:
        mr = await gitlab_client.get_mr(mr_iid)

        if mr.state != "opened":
            log.info("MR is no longer open", mr_iid=mr_iid, state=mr.state)
            return False

        if settings.queue_label not in mr.labels and settings.hotfix_label not in mr.labels:
            log.info("MR no longer has queue or hotfix label", mr_iid=mr_iid)
            return False

        return True

    except GitLabNotFoundError:
        log.warning("MR not found", mr_iid=mr_iid)
        return False


async def wait_for_rebase_completion(
    gitlab_client: GitLabClient,
    mr_iid: int,
    timeout_seconds: int,
    poll_interval_seconds: int,
    operation_name: str,
    shutdown_event: asyncio.Event,
    *,
    fetch_conflict_details: bool = False,
    conflict_error_prefix: str = "Rebase conflict",
    timeout_error_message: str = "Rebase timeout",
    shutdown_error_message: str = "Shutdown requested during rebase wait",
) -> None:
    """Wait for a GitLab rebase operation to complete.

    Shared implementation for ``RebaseHandler.wait_for_rebase_quick`` and
    ``RebaseDuringTestingHandler._wait_for_rebase``.

    Args:
        gitlab_client: GitLab API client.
        mr_iid: MR internal ID.
        timeout_seconds: Maximum time to wait.
        poll_interval_seconds: Interval between status checks.
        operation_name: Label for logging / polling config.
        shutdown_event: Event to monitor for graceful shutdown.
        fetch_conflict_details: If True, fetch conflicted file list on conflict.
        conflict_error_prefix: Prefix for the GitLabConflictError message.
        timeout_error_message: Message for timeout GitLabAPIError.
        shutdown_error_message: Message for shutdown GitLabAPIError.

    Raises:
        GitLabConflictError: If rebase results in conflicts.
        GitLabAPIError: If rebase times out or shutdown requested.
    """

    async def check_rebase() -> tuple[PollStatus, bool | None]:
        rebase_in_progress, has_conflicts = await gitlab_client.check_rebase_status(mr_iid)

        if has_conflicts:
            if fetch_conflict_details:
                conflicted_files = await gitlab_client.get_mr_conflicts(mr_iid)
                files_info = f": {conflicted_files}" if conflicted_files else ""
                raise GitLabConflictError(f"{conflict_error_prefix}{files_info}")
            raise GitLabConflictError(conflict_error_prefix)

        if not rebase_in_progress:
            return PollStatus.DONE, True

        return PollStatus.CONTINUE, None

    config = PollingConfig(
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        operation_name=operation_name,
    )
    outcome = await poll_until_done(config, check_rebase, shutdown_event)

    if outcome.completed and outcome.result:
        return

    if outcome.shutdown_requested:
        raise GitLabAPIError(shutdown_error_message)

    if outcome.timed_out:
        raise GitLabAPIError(timeout_error_message)


__all__: list[str] = ["interruptible_sleep", "verify_mr_in_queue", "wait_for_rebase_completion"]
