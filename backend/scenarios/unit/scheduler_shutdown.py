"""Unit tests for QueueScheduler shutdown behavior.

Tests the scheduler's graceful shutdown functionality and cancellation handling.
"""

from __future__ import annotations

import asyncio
import contextlib

import vedro
from vedro import scenario

from gitlab_queue.clients.gitlab import GitLabAPIError
from gitlab_queue.core.scheduler import QueueScheduler
from scenarios.fakes import FakeGitLabClient, FakeQueueManager, FakeSettings


@scenario()
async def scheduler_shutdown_stops_polling_loop():
    """Test that requesting shutdown stops the polling loop."""
    with vedro.given:
        gitlab_client = FakeGitLabClient()
        queue_manager = FakeQueueManager()
        settings = FakeSettings(poll_interval_seconds=0.1)

        scheduler = QueueScheduler(
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            settings=settings,
        )

    with vedro.when:
        # Start scheduler in background
        scheduler_task = asyncio.create_task(scheduler.run())

        # Let it run for a moment
        await asyncio.sleep(0.05)

        # Request shutdown
        scheduler.request_shutdown()

        # Wait for task to complete
        try:
            await asyncio.wait_for(scheduler_task, timeout=1.0)
            shutdown_successful = True
        except TimeoutError:
            shutdown_successful = False
            scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await scheduler_task

    with vedro.then:
        # Verify scheduler stopped gracefully
        assert shutdown_successful is True
        assert scheduler.is_shutdown_requested is True


@scenario()
async def scheduler_completes_current_sync_before_shutdown():
    """Test that scheduler completes current sync operation before shutting down."""
    with vedro.given:
        sync_started = asyncio.Event()
        sync_completed = asyncio.Event()

        class SlowGitLabClient(FakeGitLabClient):
            async def list_mrs_with_label(self, label: str, *, state: str = "opened") -> list[object]:
                self.list_mrs_calls.append(label)
                sync_started.set()
                await asyncio.sleep(0.2)  # Simulate slow API call
                sync_completed.set()
                return []

        gitlab_client = SlowGitLabClient()
        queue_manager = FakeQueueManager()
        settings = FakeSettings(poll_interval_seconds=10)

        scheduler = QueueScheduler(
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            settings=settings,
        )

    with vedro.when:
        # Start scheduler in background
        scheduler_task = asyncio.create_task(scheduler.run())

        # Wait for sync to start
        await sync_started.wait()

        # Request shutdown while sync is in progress
        scheduler.request_shutdown()

        # Wait for task to complete
        try:
            await asyncio.wait_for(scheduler_task, timeout=1.0)
            shutdown_successful = True
        except TimeoutError:
            shutdown_successful = False
            scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await scheduler_task

    with vedro.then:
        # Verify sync was completed before shutdown
        assert sync_completed.is_set() is True
        assert shutdown_successful is True


@scenario()
async def scheduler_handles_cancellation_during_sleep():
    """Test that scheduler handles cancellation during sleep between polls."""
    with vedro.given:
        gitlab_client = FakeGitLabClient()
        queue_manager = FakeQueueManager()
        settings = FakeSettings(poll_interval_seconds=60)

        scheduler = QueueScheduler(
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            settings=settings,
        )

    with vedro.when:
        # Start scheduler in background
        scheduler_task = asyncio.create_task(scheduler.run())

        # Let it complete first sync and start sleeping
        await asyncio.sleep(0.1)

        # Cancel the task (simulating forced shutdown)
        scheduler_task.cancel()

        # Try to await the cancelled task
        try:
            await scheduler_task
            was_cancelled = False
        except asyncio.CancelledError:
            was_cancelled = True

    with vedro.then:
        # Verify task was properly cancelled
        assert was_cancelled is True
        # Verify at least one sync was attempted
        assert len(gitlab_client.list_mrs_calls) >= 1


@scenario()
async def scheduler_continues_after_sync_error():
    """Test that scheduler continues polling after a sync error."""
    with vedro.given:
        # First two calls fail (queue label + hotfix label in first sync),
        # then succeed for subsequent syncs
        gitlab_client = FakeGitLabClient(
            list_mrs_error_sequence=[
                GitLabAPIError("Temporary error", status_code=500),
                # After this error, the sequence is exhausted and normal behavior resumes
            ],
        )
        queue_manager = FakeQueueManager()
        settings = FakeSettings(poll_interval_seconds=0.1)

        scheduler = QueueScheduler(
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            settings=settings,
        )

    with vedro.when:
        # Start scheduler in background
        scheduler_task = asyncio.create_task(scheduler.run())

        # Let it run for enough time to do 2+ syncs
        await asyncio.sleep(0.3)

        # Request shutdown
        scheduler.request_shutdown()

        # Wait for task to complete
        try:
            await asyncio.wait_for(scheduler_task, timeout=1.0)
        except TimeoutError:
            scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await scheduler_task

    with vedro.then:
        # Verify scheduler continued after error and made multiple attempts
        # At least 3 calls: 1 failed + 2 successful (queue + hotfix label)
        assert len(gitlab_client.list_mrs_calls) >= 3


@scenario()
async def scheduler_sync_lock_prevents_concurrent_syncs():
    """Test that sync lock prevents concurrent sync operations."""
    with vedro.given:
        sync_operations = 0
        concurrent_syncs = 0
        max_concurrent = 0

        class TrackingQueueManager(FakeQueueManager):
            async def get_active_queue(self, project_id: int | None = None) -> list[object]:
                nonlocal sync_operations, concurrent_syncs, max_concurrent
                concurrent_syncs += 1
                max_concurrent = max(max_concurrent, concurrent_syncs)
                sync_operations += 1
                await asyncio.sleep(0.1)  # Simulate work
                concurrent_syncs -= 1
                return []

        gitlab_client = FakeGitLabClient()
        queue_manager = TrackingQueueManager()
        settings = FakeSettings()

        scheduler = QueueScheduler(
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            settings=settings,
        )

    with vedro.when:
        # Try to run multiple syncs concurrently
        sync_tasks = [
            asyncio.create_task(scheduler.sync_queue()),
            asyncio.create_task(scheduler.sync_queue()),
            asyncio.create_task(scheduler.sync_queue()),
        ]

        # Wait for all to complete
        await asyncio.gather(*sync_tasks)

    with vedro.then:
        # Verify syncs ran sequentially (lock prevented concurrency)
        assert sync_operations == 3
        assert max_concurrent == 1  # Never more than 1 concurrent sync
