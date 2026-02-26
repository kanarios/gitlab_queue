"""Helpers for polling module test scenarios."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from gitlab_queue.core.polling import PollingConfig, PollStatus

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def create_polling_config(
    timeout_seconds: float = 10.0,
    poll_interval_seconds: float = 1.0,
    operation_name: str = "test_polling",
) -> PollingConfig:
    """Create PollingConfig for tests."""
    return PollingConfig(
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        operation_name=operation_name,
    )


def create_shutdown_event(is_set: bool = False) -> asyncio.Event:
    """Create shutdown event for tests."""
    event = asyncio.Event()
    if is_set:
        event.set()
    return event


def create_immediate_done_poll_fn(
    result: object = "done_result",
) -> Callable[[], Awaitable[tuple[PollStatus, object | None]]]:
    """Create poll_fn that returns DONE immediately."""

    async def poll_fn() -> tuple[PollStatus, object | None]:
        return PollStatus.DONE, result

    return poll_fn


def create_never_done_poll_fn() -> Callable[[], Awaitable[tuple[PollStatus, None]]]:
    """Create poll_fn that always returns CONTINUE."""

    async def poll_fn() -> tuple[PollStatus, None]:
        return PollStatus.CONTINUE, None

    return poll_fn


def create_counting_poll_fn(
    done_after: int,
    result: object = "counted_result",
) -> tuple[Callable[[], Awaitable[tuple[PollStatus, object | None]]], list[int]]:
    """Create poll_fn that returns DONE on the Nth call.

    Args:
        done_after: Call number on which to return DONE. Must be >= 1.
                    For done_after=3, calls 1-2 return CONTINUE, call 3 returns DONE.

    Returns:
        Tuple of (poll_fn, call_counter_list).
        call_counter_list is mutated on each call.

    Raises:
        ValueError: If done_after < 1.
    """
    if done_after < 1:
        raise ValueError(f"done_after must be >= 1, got {done_after}")
    counter: list[int] = [0]

    async def poll_fn() -> tuple[PollStatus, object | None]:
        counter[0] += 1
        if counter[0] >= done_after:
            return PollStatus.DONE, result
        return PollStatus.CONTINUE, None

    return poll_fn, counter


def create_instant_sleep_fn() -> tuple[Callable[[float, asyncio.Event], Awaitable[bool]], list[float]]:
    """Create sleep_fn that completes instantly.

    Returns:
        Tuple of (sleep_fn, sleep_durations_list).
        sleep_durations_list records each sleep duration.
    """
    durations: list[float] = []

    async def sleep_fn(seconds: float, _shutdown_event: asyncio.Event) -> bool:
        durations.append(seconds)
        return True

    return sleep_fn, durations


def create_shutdown_sleep_fn() -> Callable[[float, asyncio.Event], Awaitable[bool]]:
    """Create sleep_fn that simulates shutdown interruption."""

    async def sleep_fn(_seconds: float, _shutdown_event: asyncio.Event) -> bool:
        return False

    return sleep_fn


__all__ = [
    "create_counting_poll_fn",
    "create_immediate_done_poll_fn",
    "create_instant_sleep_fn",
    "create_never_done_poll_fn",
    "create_polling_config",
    "create_shutdown_event",
    "create_shutdown_sleep_fn",
]
