"""Unit tests for QueueScheduler sync operations.

Tests the polling fallback scheduler's ability to synchronize queue state
with GitLab, including adding missing MRs and removing orphaned entries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import vedro
from vedro import scenario

if TYPE_CHECKING:
    from gitlab_queue.core.scheduler import SyncStats


@scenario()
async def sync_adds_missing_mrs_to_queue():
    """Test that sync adds MRs from GitLab that are missing in queue."""
    with vedro.given:
        # Mock GitLab client
        gitlab_client = AsyncMock()

        # Create real MergeRequest objects (not mocks)
        from gitlab_queue.models.mr import Author, MergeRequest

        mr1 = MergeRequest(
            iid=1,
            title="MR 1",
            state="opened",
            labels=["merge_queue"],
            sha="abc123",
            source_branch="feature-1",
            target_branch="master",
            merge_status="can_be_merged",
            has_conflicts=False,
            rebase_in_progress=False,
            author=Author(id=1, name="Alice", username="alice", avatar_url=None),
            web_url="https://gitlab.com/project/-/merge_requests/1",
        )
        mr2 = MergeRequest(
            iid=2,
            title="MR 2",
            state="opened",
            labels=["merge_queue", "hotfix"],
            sha="def456",
            source_branch="feature-2",
            target_branch="master",
            merge_status="can_be_merged",
            has_conflicts=False,
            rebase_in_progress=False,
            author=Author(id=2, name="Bob", username="bob", avatar_url=None),
            web_url="https://gitlab.com/project/-/merge_requests/2",
        )
        gitlab_client.list_mrs_with_label = AsyncMock(return_value=[mr1, mr2])
        gitlab_client.get_mr = AsyncMock(side_effect=[mr1, mr2])

        # Mock queue manager with empty queue
        queue_manager = AsyncMock()
        queue_manager.get_active_queue = AsyncMock(return_value=[])
        queue_manager.add_to_queue = AsyncMock()

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
        stats: SyncStats = await scheduler.sync_queue()

    with vedro.then:
        # Verify MRs were added to queue
        assert stats.mrs_in_gitlab == 2
        assert stats.mrs_in_queue == 0
        assert stats.added == 2
        assert stats.removed == 0
        assert stats.unchanged == 0

        # Verify add_to_queue was called for both MRs
        assert queue_manager.add_to_queue.call_count == 2

        # Verify hotfix flag was set correctly
        calls = queue_manager.add_to_queue.call_args_list
        # First MR (no hotfix label)
        assert calls[0].kwargs["is_hotfix"] is False
        # Second MR (has hotfix label)
        assert calls[1].kwargs["is_hotfix"] is True


@scenario()
async def sync_removes_orphaned_mrs_from_queue():
    """Test that sync removes MRs from queue that are no longer in GitLab."""
    with vedro.given:
        # Mock GitLab client
        gitlab_client = AsyncMock()

        # GitLab returns only MR 1 (MR 2 has been closed/unlabeled)
        from gitlab_queue.models.mr import Author, MergeRequest

        mr1 = MergeRequest(
            iid=1,
            title="MR 1",
            state="opened",
            labels=["merge_queue"],
            sha="abc123",
            source_branch="feature-1",
            target_branch="master",
            merge_status="can_be_merged",
            has_conflicts=False,
            rebase_in_progress=False,
            author=Author(id=1, name="Alice", username="alice", avatar_url=None),
            web_url="https://gitlab.com/project/-/merge_requests/1",
        )
        gitlab_client.list_mrs_with_label = AsyncMock(return_value=[mr1])

        # MR 2 exists but is closed
        mr2_closed = Mock(
            iid=2,
            title="MR 2",
            labels=["merge_queue"],
            state="closed",
        )
        gitlab_client.get_mr = AsyncMock(return_value=mr2_closed)

        # Mock queue manager with 2 items
        queue_item1 = Mock(
            mr_iid=1,
            state="queued",
            queued_at=datetime.now(UTC),
        )
        queue_item2 = Mock(
            mr_iid=2,
            state="queued",
            queued_at=datetime.now(UTC),
        )
        queue_manager = AsyncMock()
        queue_manager.get_active_queue = AsyncMock(return_value=[queue_item1, queue_item2])
        queue_manager.remove_from_queue = AsyncMock()

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
        stats: SyncStats = await scheduler.sync_queue()

    with vedro.then:
        # Verify orphaned MR was removed
        assert stats.mrs_in_gitlab == 1
        assert stats.mrs_in_queue == 2
        assert stats.added == 0
        assert stats.removed == 1
        assert stats.unchanged == 1

        # Verify remove_from_queue was called for MR 2
        queue_manager.remove_from_queue.assert_awaited_once_with(2)


@scenario()
async def sync_handles_gitlab_api_errors_gracefully():
    """Test that sync handles GitLab API errors without crashing."""
    with vedro.given:
        # Mock GitLab client that raises error
        gitlab_client = AsyncMock()
        from gitlab_queue.clients.gitlab import GitLabAPIError

        gitlab_client.list_mrs_with_label = AsyncMock(
            side_effect=GitLabAPIError("API rate limit exceeded", status_code=429)
        )

        # Mock queue manager
        queue_manager = AsyncMock()

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
        # Should not raise exception
        try:
            await scheduler.sync_queue()
            error_occurred = False
        except GitLabAPIError:
            error_occurred = True

    with vedro.then:
        # Verify API error was caught and handled
        assert error_occurred is True
        # Queue operations should not have been called
        assert queue_manager.get_active_queue.called is False
        assert queue_manager.add_to_queue.called is False
        assert queue_manager.remove_from_queue.called is False


@scenario()
async def sync_does_not_duplicate_existing_mrs():
    """Test that sync does not duplicate MRs already in the queue."""
    with vedro.given:
        # Mock GitLab client
        gitlab_client = AsyncMock()

        # GitLab returns 2 MRs
        from gitlab_queue.models.mr import Author, MergeRequest

        mr1 = MergeRequest(
            iid=1,
            title="MR 1",
            state="opened",
            labels=["merge_queue"],
            sha="abc123",
            source_branch="feature-1",
            target_branch="master",
            merge_status="can_be_merged",
            has_conflicts=False,
            rebase_in_progress=False,
            author=Author(id=1, name="Alice", username="alice", avatar_url=None),
            web_url="https://gitlab.com/project/-/merge_requests/1",
        )
        mr2 = MergeRequest(
            iid=2,
            title="MR 2",
            state="opened",
            labels=["merge_queue"],
            sha="def456",
            source_branch="feature-2",
            target_branch="master",
            merge_status="can_be_merged",
            has_conflicts=False,
            rebase_in_progress=False,
            author=Author(id=2, name="Bob", username="bob", avatar_url=None),
            web_url="https://gitlab.com/project/-/merge_requests/2",
        )
        gitlab_client.list_mrs_with_label = AsyncMock(return_value=[mr1, mr2])

        # Queue already contains both MRs
        queue_item1 = Mock(
            mr_iid=1,
            state="queued",
            queued_at=datetime.now(UTC),
        )
        queue_item2 = Mock(
            mr_iid=2,
            state="testing",  # Different state but still active
            queued_at=datetime.now(UTC),
        )
        queue_manager = AsyncMock()
        queue_manager.get_active_queue = AsyncMock(return_value=[queue_item1, queue_item2])
        queue_manager.add_to_queue = AsyncMock()

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
        stats: SyncStats = await scheduler.sync_queue()

    with vedro.then:
        # Verify no MRs were added or removed
        assert stats.mrs_in_gitlab == 2
        assert stats.mrs_in_queue == 2
        assert stats.added == 0
        assert stats.removed == 0
        assert stats.unchanged == 2

        # Verify add_to_queue was not called
        assert queue_manager.add_to_queue.called is False
        # Verify remove_from_queue was not called
        assert queue_manager.remove_from_queue.called is False


@scenario()
async def sync_removes_mr_with_removed_queue_label():
    """Test that sync removes MR when queue label is removed."""
    with vedro.given:
        # Mock GitLab client
        gitlab_client = AsyncMock()

        # GitLab returns empty list (no MRs with queue label)
        gitlab_client.list_mrs_with_label = AsyncMock(return_value=[])

        # MR exists but no longer has queue label
        mr_without_label = Mock(
            iid=1,
            title="MR 1",
            labels=["review"],  # No queue_label
            state="opened",
        )
        gitlab_client.get_mr = AsyncMock(return_value=mr_without_label)

        # Queue contains the MR
        queue_item = Mock(
            mr_iid=1,
            state="queued",
            queued_at=datetime.now(UTC),
        )
        queue_manager = AsyncMock()
        queue_manager.get_active_queue = AsyncMock(return_value=[queue_item])
        queue_manager.remove_from_queue = AsyncMock()

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
        stats: SyncStats = await scheduler.sync_queue()

    with vedro.then:
        # Verify MR was removed due to missing label
        assert stats.mrs_in_gitlab == 0
        assert stats.mrs_in_queue == 1
        assert stats.added == 0
        assert stats.removed == 1
        assert stats.unchanged == 0

        # Verify remove_from_queue was called
        queue_manager.remove_from_queue.assert_awaited_once_with(1)


@scenario()
async def sync_handles_404_mr_not_found():
    """Test that sync removes MR when it returns 404 from GitLab."""
    with vedro.given:
        # Mock GitLab client
        gitlab_client = AsyncMock()
        from gitlab_queue.clients.gitlab import GitLabNotFoundError

        # GitLab returns empty list
        gitlab_client.list_mrs_with_label = AsyncMock(return_value=[])

        # MR no longer exists (404)
        gitlab_client.get_mr = AsyncMock(side_effect=GitLabNotFoundError("MR not found", status_code=404))

        # Queue contains the missing MR
        queue_item = Mock(
            mr_iid=999,
            state="queued",
            queued_at=datetime.now(UTC),
        )
        queue_manager = AsyncMock()
        queue_manager.get_active_queue = AsyncMock(return_value=[queue_item])
        queue_manager.remove_from_queue = AsyncMock()

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
        stats: SyncStats = await scheduler.sync_queue()

    with vedro.then:
        # Verify MR was removed due to 404
        assert stats.mrs_in_gitlab == 0
        assert stats.mrs_in_queue == 1
        assert stats.added == 0
        assert stats.removed == 1
        assert stats.unchanged == 0

        # Verify remove_from_queue was called
        queue_manager.remove_from_queue.assert_awaited_once_with(999)
