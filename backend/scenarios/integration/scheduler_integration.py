"""Integration tests for QueueScheduler with other components.

Tests the scheduler's interaction with GitLab client, queue manager,
and the overall system behavior.
"""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

import vedro
from vedro import scenario


@scenario()
async def scheduler_integrates_with_real_queue_manager():
    """Test scheduler integration with real queue manager and SQLite."""
    with vedro.given:
        # Create in-memory database
        from gitlab_queue.db.database import Database

        database = Database("sqlite+aiosqlite:///:memory:")
        await database.initialize()

        # Create real queue manager
        from gitlab_queue.core.queue import QueueManager

        queue_manager = QueueManager(db=database)
        await queue_manager.ensure_schema()

        # Mock GitLab client
        from unittest.mock import AsyncMock

        gitlab_client = AsyncMock()

        # Create mock MRs from GitLab
        from gitlab_queue.models.mr import Author, MergeRequest

        mr1 = MergeRequest(
            iid=1,
            title="Feature A",
            state="opened",
            labels=["merge_queue"],
            sha="abc123",
            source_branch="feature-a",
            target_branch="master",
            merge_status="can_be_merged",
            has_conflicts=False,
            rebase_in_progress=False,
            author=Author(
                name="Alice",
                username="alice",
                avatar_url="https://example.com/alice.jpg",
            ),
            web_url="https://gitlab.com/project/-/merge_requests/1",
        )

        mr2 = MergeRequest(
            iid=2,
            title="Hotfix B",
            state="opened",
            labels=["merge_queue", "hotfix"],
            sha="def456",
            source_branch="hotfix-b",
            target_branch="master",
            merge_status="can_be_merged",
            has_conflicts=False,
            rebase_in_progress=False,
            author=Author(
                name="Bob",
                username="bob",
                avatar_url="https://example.com/bob.jpg",
            ),
            web_url="https://gitlab.com/project/-/merge_requests/2",
        )

        gitlab_client.list_mrs_with_label = AsyncMock(return_value=[mr1, mr2])

        # Mock settings
        settings = Mock(
            queue_label="merge_queue",
            hotfix_label="hotfix",
            poll_interval_seconds=30,
        )

        # Create scheduler
        from gitlab_queue.core.scheduler import create_scheduler

        scheduler = create_scheduler(
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            settings=settings,
        )

    with vedro.when:
        # Run sync
        stats = await scheduler.sync_queue()

        # Get queue state after sync
        queue_items = await queue_manager.get_active_queue()
        queue_stats = await queue_manager.get_queue_stats()

    with vedro.then:
        # Verify MRs were added
        assert stats.added == 2
        assert stats.mrs_in_gitlab == 2

        # Verify queue contains both MRs
        assert len(queue_items) == 2

        # Verify hotfix is first (priority)
        assert queue_items[0].mr_iid == 2  # Hotfix
        assert queue_items[0].is_hotfix is True
        assert queue_items[1].mr_iid == 1  # Regular MR
        assert queue_items[1].is_hotfix is False

        # Verify queue stats
        assert queue_stats["queued"] == 2
        assert queue_stats["rebasing"] == 0
        assert queue_stats["testing"] == 0
        assert queue_stats["merging"] == 0

    # Cleanup
    await database.close()


@scenario()
async def scheduler_handles_concurrent_webhook_and_polling():
    """Test that scheduler handles concurrent operations with webhooks."""
    with vedro.given:
        # Create in-memory database
        from gitlab_queue.db.database import Database

        database = Database("sqlite+aiosqlite:///:memory:")
        await database.initialize()

        # Create real queue manager
        from gitlab_queue.core.queue import QueueManager

        queue_manager = QueueManager(db=database)
        await queue_manager.ensure_schema()

        # Mock GitLab client
        from unittest.mock import AsyncMock

        gitlab_client = AsyncMock()

        # Create mock MR
        from gitlab_queue.models.mr import Author, MergeRequest

        mr1 = MergeRequest(
            iid=1,
            title="Feature A",
            state="opened",
            labels=["merge_queue"],
            sha="abc123",
            source_branch="feature-a",
            target_branch="master",
            merge_status="can_be_merged",
            has_conflicts=False,
            rebase_in_progress=False,
            author=Author(
                name="Alice",
                username="alice",
                avatar_url=None,
            ),
            web_url="https://gitlab.com/project/-/merge_requests/1",
        )

        # Initially empty, then returns MR
        call_count = 0

        async def dynamic_list_mrs(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return []  # First call: empty
            return [mr1]  # Subsequent calls: MR present

        gitlab_client.list_mrs_with_label = AsyncMock(side_effect=dynamic_list_mrs)

        # Mock settings
        settings = Mock(
            queue_label="merge_queue",
            hotfix_label="hotfix",
            poll_interval_seconds=30,
        )

        # Create scheduler
        from gitlab_queue.core.scheduler import create_scheduler

        scheduler = create_scheduler(
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            settings=settings,
        )

    with vedro.when:
        # First sync - queue empty
        stats1 = await scheduler.sync_queue()

        # Simulate webhook adding MR to queue (concurrent operation)
        await queue_manager.add_to_queue(mr1, is_hotfix=False)

        # Second sync - MR already in queue from webhook
        stats2 = await scheduler.sync_queue()

        # Get final queue state
        queue_items = await queue_manager.get_active_queue()

    with vedro.then:
        # First sync found nothing
        assert stats1.added == 0
        assert stats1.mrs_in_gitlab == 0

        # Second sync found MR but didn't duplicate it
        assert stats2.added == 0  # Not added again
        assert stats2.unchanged == 1  # Already present
        assert stats2.mrs_in_gitlab == 1

        # Queue contains exactly one MR (no duplication)
        assert len(queue_items) == 1
        assert queue_items[0].mr_iid == 1

    # Cleanup
    await database.close()


@scenario()
async def scheduler_recovers_from_gitlab_outage():
    """Test that scheduler recovers and syncs after GitLab API outage."""
    with vedro.given:
        # Create in-memory database
        from gitlab_queue.db.database import Database

        database = Database("sqlite+aiosqlite:///:memory:")
        await database.initialize()

        # Create real queue manager
        from gitlab_queue.core.queue import QueueManager

        queue_manager = QueueManager(db=database)
        await queue_manager.ensure_schema()

        # Mock GitLab client
        from unittest.mock import AsyncMock

        gitlab_client = AsyncMock()

        # Create mock MR
        from gitlab_queue.models.mr import Author, MergeRequest

        mr1 = MergeRequest(
            iid=1,
            title="Feature A",
            state="opened",
            labels=["merge_queue"],
            sha="abc123",
            source_branch="feature-a",
            target_branch="master",
            merge_status="can_be_merged",
            has_conflicts=False,
            rebase_in_progress=False,
            author=Author(
                name="Alice",
                username="alice",
                avatar_url=None,
            ),
            web_url="https://gitlab.com/project/-/merge_requests/1",
        )

        # Simulate outage then recovery
        call_count = 0

        async def outage_then_recovery(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                from gitlab_queue.clients.gitlab import GitLabServerError

                raise GitLabServerError("Service unavailable", status_code=503)
            return [mr1]  # Service recovered

        gitlab_client.list_mrs_with_label = AsyncMock(side_effect=outage_then_recovery)

        # Mock settings with short poll interval
        settings = Mock(
            queue_label="merge_queue",
            hotfix_label="hotfix",
            poll_interval_seconds=0.1,  # Quick polling for test
        )

        # Create scheduler
        from gitlab_queue.core.scheduler import create_scheduler

        scheduler = create_scheduler(
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            settings=settings,
        )

    with vedro.when:
        # Start scheduler
        scheduler_task = asyncio.create_task(scheduler.run())

        # Let it run through several poll cycles
        await asyncio.sleep(0.5)

        # Stop scheduler
        scheduler.request_shutdown()
        await asyncio.wait_for(scheduler_task, timeout=2.0)

        # Get final queue state
        queue_items = await queue_manager.get_active_queue()

    with vedro.then:
        # Verify scheduler recovered and added MR after outage
        assert call_count >= 3  # Failed twice, succeeded at least once
        assert len(queue_items) == 1
        assert queue_items[0].mr_iid == 1

    # Cleanup
    await database.close()


@scenario()
async def scheduler_removes_orphaned_entries_after_mr_closed():
    """Test that scheduler removes MRs that were closed outside of queue."""
    with vedro.given:
        # Create in-memory database
        from gitlab_queue.db.database import Database

        database = Database("sqlite+aiosqlite:///:memory:")
        await database.initialize()

        # Create real queue manager
        from gitlab_queue.core.queue import QueueManager

        queue_manager = QueueManager(db=database)
        await queue_manager.ensure_schema()

        # Add MRs to queue initially
        from gitlab_queue.models.mr import Author, MergeRequest

        mr1 = MergeRequest(
            iid=1,
            title="Feature A",
            state="opened",
            labels=["merge_queue"],
            sha="abc123",
            source_branch="feature-a",
            target_branch="master",
            merge_status="can_be_merged",
            has_conflicts=False,
            rebase_in_progress=False,
            author=Author(
                name="Alice",
                username="alice",
                avatar_url=None,
            ),
            web_url="https://gitlab.com/project/-/merge_requests/1",
        )

        mr2 = MergeRequest(
            iid=2,
            title="Feature B",
            state="opened",
            labels=["merge_queue"],
            sha="def456",
            source_branch="feature-b",
            target_branch="master",
            merge_status="can_be_merged",
            has_conflicts=False,
            rebase_in_progress=False,
            author=Author(
                name="Bob",
                username="bob",
                avatar_url=None,
            ),
            web_url="https://gitlab.com/project/-/merge_requests/2",
        )

        # Add both to queue
        await queue_manager.add_to_queue(mr1, is_hotfix=False)
        await queue_manager.add_to_queue(mr2, is_hotfix=False)

        # Mock GitLab client - MR2 was closed
        from unittest.mock import AsyncMock

        gitlab_client = AsyncMock()

        # Only MR1 remains with label
        gitlab_client.list_mrs_with_label = AsyncMock(return_value=[mr1])

        # MR2 is now closed
        mr2_closed = MergeRequest(
            iid=2,
            title="Feature B",
            state="closed",  # Now closed
            labels=["merge_queue"],
            sha="def456",
            source_branch="feature-b",
            target_branch="master",
            merge_status="can_be_merged",
            has_conflicts=False,
            rebase_in_progress=False,
            author=Author(
                name="Bob",
                username="bob",
                avatar_url=None,
            ),
            web_url="https://gitlab.com/project/-/merge_requests/2",
        )
        gitlab_client.get_mr = AsyncMock(return_value=mr2_closed)

        # Mock settings
        settings = Mock(
            queue_label="merge_queue",
            hotfix_label="hotfix",
            poll_interval_seconds=30,
        )

        # Create scheduler
        from gitlab_queue.core.scheduler import create_scheduler

        scheduler = create_scheduler(
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            settings=settings,
        )

    with vedro.when:
        # Run sync
        stats = await scheduler.sync_queue()

        # Get queue state after sync
        queue_items = await queue_manager.get_active_queue()

    with vedro.then:
        # Verify orphaned MR was removed
        assert stats.removed == 1
        assert stats.unchanged == 1

        # Only MR1 remains in queue
        assert len(queue_items) == 1
        assert queue_items[0].mr_iid == 1

        # MR2 was marked as removed
        mr2_state = await queue_manager.get_mr_state(2)
        assert mr2_state["status"] == "removed"

    # Cleanup
    await database.close()
