"""Unit tests for QueueScheduler sync operations.

Tests the polling fallback scheduler's ability to synchronize queue state
with GitLab, including adding missing MRs and removing orphaned entries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import vedro
from vedro import scenario

from gitlab_queue.clients.gitlab import GitLabAPIError, GitLabNotFoundError
from scenarios.fakes import FakeGitLabClient, FakeQueueManager, FakeSettings, create_mr

if TYPE_CHECKING:
    from gitlab_queue.core.scheduler import SyncStats
    from gitlab_queue.models.mr import MergeRequest


def _make_mr(iid: int, labels: list[str] | None = None) -> MergeRequest:
    """Create a MergeRequest with sensible defaults."""
    return create_mr(
        iid=iid,
        labels=labels or ["merge_queue"],
        source_branch=f"feature-{iid}",
    )


def _make_queue_item(queue_manager: FakeQueueManager, mr_iid: int, state: str = "queued") -> None:
    """Add a queue item to the fake queue manager."""
    from datetime import UTC, datetime

    from gitlab_queue.models.queue_item import QueueItem

    item = QueueItem(
        mr_iid=mr_iid,
        title=f"MR {mr_iid}",
        author_name="Test",
        author_username="test",
        target_branch="master",
        state=state,
        queued_at=datetime.now(UTC),
        is_hotfix=False,
        labels=["merge_queue"],
    )
    queue_manager.add_item(item)


@scenario()
async def sync_adds_missing_mrs_to_queue():
    """Test that sync adds MRs from GitLab that are missing in queue."""
    with vedro.given:
        mr1 = _make_mr(iid=1)
        mr2 = _make_mr(iid=2, labels=["merge_queue", "hotfix"])

        gitlab_client = FakeGitLabClient(listed_mrs=[mr1, mr2])
        queue_manager = FakeQueueManager()
        settings = FakeSettings()

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
        assert stats.mrs_in_queue == 2  # Updated after finalization
        assert stats.added == 2
        assert stats.removed == 0
        assert stats.unchanged == 0

        # Verify add_to_queue was called for both MRs
        assert len(queue_manager.add_to_queue_calls) == 2

        # Verify hotfix flag was set correctly
        calls = queue_manager.add_to_queue_calls
        # First MR (no hotfix label)
        assert calls[0]["is_hotfix"] is False
        # Second MR (has hotfix label)
        assert calls[1]["is_hotfix"] is True


@scenario()
async def sync_removes_orphaned_mrs_from_queue():
    """Test that sync removes MRs from queue that are no longer in GitLab."""
    with vedro.given:
        mr1 = _make_mr(iid=1)

        # GitLab returns only MR 1 (MR 2 has been closed/unlabeled)
        gitlab_client = FakeGitLabClient(
            listed_mrs=[mr1],
            # MR 2 exists but is closed
            mr_responses={2: create_mr(iid=2, state="closed", labels=["merge_queue"])},
        )

        queue_manager = FakeQueueManager()
        _make_queue_item(queue_manager, mr_iid=1)
        _make_queue_item(queue_manager, mr_iid=2)

        settings = FakeSettings()

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
        assert stats.mrs_in_queue == 1  # finalize_sync updates to current queue size
        assert stats.added == 0
        assert stats.removed == 1
        assert stats.unchanged == 1

        # Verify remove_from_queue was called for MR 2
        assert queue_manager.remove_calls == [2]


@scenario()
async def sync_handles_gitlab_api_errors_gracefully():
    """Test that sync handles GitLab API errors without crashing."""
    with vedro.given:
        gitlab_client = FakeGitLabClient(
            list_mrs_error=GitLabAPIError("API rate limit exceeded", status_code=429),
        )
        queue_manager = FakeQueueManager()
        settings = FakeSettings()

        from gitlab_queue.core.scheduler import QueueScheduler

        scheduler = QueueScheduler(
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            settings=settings,
        )

    with vedro.when:
        # Should raise exception (scheduler.run() catches it, but sync_queue() propagates)
        try:
            await scheduler.sync_queue()
            error_occurred = False
        except GitLabAPIError:
            error_occurred = True

    with vedro.then:
        # Verify API error was raised
        assert error_occurred is True
        # Queue operations should not have been called
        assert len(queue_manager.add_to_queue_calls) == 0
        assert len(queue_manager.remove_calls) == 0


@scenario()
async def sync_does_not_duplicate_existing_mrs():
    """Test that sync does not duplicate MRs already in the queue."""
    with vedro.given:
        mr1 = _make_mr(iid=1)
        mr2 = _make_mr(iid=2)

        gitlab_client = FakeGitLabClient(listed_mrs=[mr1, mr2])

        queue_manager = FakeQueueManager()
        _make_queue_item(queue_manager, mr_iid=1)
        _make_queue_item(queue_manager, mr_iid=2, state="testing")

        settings = FakeSettings()

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
        assert len(queue_manager.add_to_queue_calls) == 0
        # Verify remove_from_queue was not called
        assert len(queue_manager.remove_calls) == 0


@scenario()
async def sync_removes_mr_with_removed_queue_label():
    """Test that sync removes MR when queue label is removed."""
    with vedro.given:
        # GitLab returns empty list (no MRs with queue label)
        gitlab_client = FakeGitLabClient(
            listed_mrs=[],
            # MR exists but no longer has queue label or hotfix label
            mr_responses={1: create_mr(iid=1, labels=["review"])},
        )

        queue_manager = FakeQueueManager()
        _make_queue_item(queue_manager, mr_iid=1)

        settings = FakeSettings()

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
        assert stats.mrs_in_queue == 0  # finalize_sync updates to current queue size
        assert stats.added == 0
        assert stats.removed == 1
        assert stats.unchanged == 0

        # Verify remove_from_queue was called
        assert queue_manager.remove_calls == [1]


@scenario()
async def sync_handles_404_mr_not_found():
    """Test that sync removes MR when it returns 404 from GitLab."""
    with vedro.given:
        gitlab_client = FakeGitLabClient(
            listed_mrs=[],
            get_mr_error=GitLabNotFoundError("MR not found", status_code=404),
        )

        queue_manager = FakeQueueManager()
        _make_queue_item(queue_manager, mr_iid=999)

        settings = FakeSettings()

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
        assert stats.mrs_in_queue == 0  # finalize_sync updates to current queue size
        assert stats.added == 0
        assert stats.removed == 1
        assert stats.unchanged == 0

        # Verify remove_from_queue was called
        assert queue_manager.remove_calls == [999]
