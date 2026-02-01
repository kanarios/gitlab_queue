"""Generic async polling utilities for eliminating code duplication.

Provides a unified polling pattern that handles:
- Timeout tracking
- Shutdown event checking
- Interruptible sleep
- Clean result reporting

This eliminates repeated polling loops across processor.py and rebase_during_testing.py.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

log = get_logger(__name__)


class PollStatus(Enum):
    """Status returned by poll function on each iteration."""

    CONTINUE = "continue"  # Keep polling
    DONE = "done"  # Operation completed


@dataclass(frozen=True)
class PollingConfig:
    """Configuration for polling operations."""

    timeout_seconds: float
    poll_interval_seconds: float
    operation_name: str = "polling"


@dataclass
class PollOutcome[T]:
    """Result of a polling operation."""

    completed: bool
    timed_out: bool
    shutdown_requested: bool
    result: T | None = None


async def _default_sleep(seconds: float, shutdown_event: asyncio.Event) -> bool:
    """Default interruptible sleep implementation.

    Args:
        seconds: Duration to sleep.
        shutdown_event: Event to check for shutdown.

    Returns:
        True if sleep completed normally, False if interrupted by shutdown.
    """
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=seconds)
        return False  # Shutdown was requested
    except TimeoutError:
        return True  # Sleep completed normally


async def poll_until_done[T](
    config: PollingConfig,
    poll_fn: Callable[[], Awaitable[tuple[PollStatus, T | None]]],
    shutdown_event: asyncio.Event,
    sleep_fn: Callable[[float, asyncio.Event], Awaitable[bool]] | None = None,
) -> PollOutcome[T]:
    """Generic polling loop with timeout and shutdown support.

    Polls until one of:
    - poll_fn returns PollStatus.DONE
    - Timeout is exceeded
    - Shutdown event is set

    Args:
        config: Polling configuration (timeout, interval, name).
        poll_fn: Async function returning (status, result). Called each iteration.
                 Should return (PollStatus.DONE, result) when complete.
        shutdown_event: Event to check for graceful shutdown.
        sleep_fn: Optional custom sleep function. Receives (seconds, shutdown_event).
                  Returns True if sleep completed, False if shutdown requested.

    Returns:
        PollOutcome with completion status and optional result.

    Example:
        async def check_status():
            status = await api.get_status()
            if status.done:
                return (PollStatus.DONE, status.result)
            return (PollStatus.CONTINUE, None)

        config = PollingConfig(timeout_seconds=60, poll_interval_seconds=5)
        outcome = await poll_until_done(config, check_status, shutdown_event)
        if outcome.completed:
            print(f"Got result: {outcome.result}")
    """
    sleep = sleep_fn or _default_sleep
    timeout = timedelta(seconds=config.timeout_seconds)
    start_time = datetime.now(UTC)

    while True:
        # Check shutdown first
        if shutdown_event.is_set():
            return PollOutcome(
                completed=False,
                timed_out=False,
                shutdown_requested=True,
                result=None,
            )

        # Check timeout
        elapsed = datetime.now(UTC) - start_time
        if elapsed > timeout:
            log.debug(
                "Polling timed out",
                operation=config.operation_name,
                elapsed_seconds=elapsed.total_seconds(),
                timeout_seconds=config.timeout_seconds,
            )
            return PollOutcome(
                completed=False,
                timed_out=True,
                shutdown_requested=False,
                result=None,
            )

        # Execute poll function
        status, result = await poll_fn()

        if status == PollStatus.DONE:
            return PollOutcome(
                completed=True,
                timed_out=False,
                shutdown_requested=False,
                result=result,
            )

        # Sleep with shutdown check
        if not await sleep(config.poll_interval_seconds, shutdown_event):
            return PollOutcome(
                completed=False,
                timed_out=False,
                shutdown_requested=True,
                result=None,
            )


__all__: list[str] = [
    "PollOutcome",
    "PollStatus",
    "PollingConfig",
    "poll_until_done",
]
