"""Unit tests for QueueScheduler shutdown behavior.

Tests the scheduler's graceful shutdown functionality and cancellation handling.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import vedro
from vedro import scenario

if TYPE_CHECKING:
    from gitlab_queue.core.scheduler import QueueScheduler


@scenario()
async def scheduler_shutdown_stops_polling_loop():
    """Test that requesting shutdown stops the polling loop."""
    with vedro.given:
        # Mock GitLab client
        gitlab_client = AsyncMock()
        gitlab_client.list_mrs_with_label = AsyncMock(return_value=[])

        # Mock queue manager
        queue_manager = AsyncMock()
        queue_manager.get_active_queue = AsyncMock(return_value=[])

        # Mock settings with short poll interval for testing
        settings = Mock(
            queue_label="merge_queue",
            hotfix_label="hotfix",
            poll_interval_seconds=0.1,  # 100ms for quick test
        )

        # Create scheduler
        from gitlab_queue.core.scheduler import QueueScheduler

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
        except asyncio.TimeoutError:
            shutdown_successful = False
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass

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

        # Mock GitLab client with slow operation
        async def slow_list_mrs(*args, **kwargs):
            sync_started.set()
            await asyncio.sleep(0.2)  # Simulate slow API call
            sync_completed.set()
            return []

        gitlab_client = AsyncMock()
        gitlab_client.list_mrs_with_label = AsyncMock(side_effect=slow_list_mrs)

        # Mock queue manager
        queue_manager = AsyncMock()
        queue_manager.get_active_queue = AsyncMock(return_value=[])

        # Mock settings
        settings = Mock(
            queue_label="merge_queue",
            hotfix_label="hotfix",
            poll_interval_seconds=10,  # Long interval so only one sync runs
        )

        # Create scheduler
        from gitlab_queue.core.scheduler import QueueScheduler

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
        except asyncio.TimeoutError:
            shutdown_successful = False
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass

    with vedro.then:
        # Verify sync was completed before shutdown
        assert sync_completed.is_set() is True
        assert shutdown_successful is True


@scenario()
async def scheduler_handles_cancellation_during_sleep():
    """Test that scheduler handles cancellation during sleep between polls."""
    with vedro.given:
        # Mock GitLab client
        gitlab_client = AsyncMock()
        gitlab_client.list_mrs_with_label = AsyncMock(return_value=[])

        # Mock queue manager
        queue_manager = AsyncMock()
        queue_manager.get_active_queue = AsyncMock(return_value=[])

        # Mock settings with long poll interval
        settings = Mock(
            queue_label="merge_queue",
            hotfix_label="hotfix",
            poll_interval_seconds=60,  # Long sleep period
        )

        # Create scheduler
        from gitlab_queue.core.scheduler import QueueScheduler

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
        assert gitlab_client.list_mrs_with_label.called is True


@scenario()
async def scheduler_continues_after_sync_error():
    """Test that scheduler continues polling after a sync error."""
    with vedro.given:
        call_count = 0

        # Mock GitLab client that fails first time, succeeds second time
        async def failing_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                from gitlab_queue.clients.gitlab import GitLabAPIError

                raise GitLabAPIError("Temporary error", status_code=500)
            return []

        gitlab_client = AsyncMock()
        gitlab_client.list_mrs_with_label = AsyncMock(side_effect=failing_then_success)

        # Mock queue manager
        queue_manager = AsyncMock()
        queue_manager.get_active_queue = AsyncMock(return_value=[])

        # Mock settings with short poll interval
        settings = Mock(
            queue_label="merge_queue",
            hotfix_label="hotfix",
            poll_interval_seconds=0.1,  # Quick polling for test
        )

        # Create scheduler
        from gitlab_queue.core.scheduler import QueueScheduler

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
        except asyncio.TimeoutError:
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass

    with vedro.then:
        # Verify scheduler continued after error and made multiple attempts
        assert gitlab_client.list_mrs_with_label.call_count >= 2
        assert call_count >= 2


@scenario()
async def scheduler_sync_lock_prevents_concurrent_syncs():
    """Test that sync lock prevents concurrent sync operations."""
    with vedro.given:
        sync_count = 0
        concurrent_syncs = 0
        max_concurrent = 0

        # Mock GitLab client with tracking
        async def tracked_list_mrs(*args, **kwargs):
            nonlocal sync_count, concurrent_syncs, max_concurrent
            concurrent_syncs += 1
            max_concurrent = max(max_concurrent, concurrent_syncs)
            sync_count += 1
            await asyncio.sleep(0.1)  # Simulate work
            concurrent_syncs -= 1
            return []

        gitlab_client = AsyncMock()
        gitlab_client.list_mrs_with_label = AsyncMock(side_effect=tracked_list_mrs)

        # Mock queue manager
        queue_manager = AsyncMock()
        queue_manager.get_active_queue = AsyncMock(return_value=[])

        # Mock settings
        settings = Mock(
            queue_label="merge_queue",
            hotfix_label="hotfix",
            poll_interval_seconds=30,
        )

        # Create scheduler
        from gitlab_queue.core.scheduler import QueueScheduler

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
        assert sync_count == 3
        assert max_concurrent == 1  # Never more than 1 concurrent sync