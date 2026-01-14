"""Test scenarios for processor handling merge conflicts.

This scenario tests how the processor handles conflicts:
1. Rebase conflicts during initial rebase
2. Conflicts discovered after rebase starts
3. Proper notification and state transitions
"""

from __future__ import annotations

import jj
from jj.mock import mocked
from scenarios.contexts.jj_gitlab_mock import get_mock_url
from vedro import given, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.config import Settings
from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.processor import MergeProcessor, ProcessingResult
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.models.mr import Author, MergeRequest


@scenario()
async def process_mr_with_immediate_conflict():
    """Test MR processing when rebase immediately returns conflict."""

    with given("MR in queue and GitLab returns rebase conflict"):
        # Setup test database and queue
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        # Create test MR
        test_mr = MergeRequest(
            iid=44,
            title="MR with Conflict",
            state="opened",
            target_branch="main",
            source_branch="feature/conflict",
            sha="conflict123",
            labels=["merge_queue"],
            author=Author(id=1, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/44",
        )

        # Add MR to queue
        await queue.add_to_queue(test_mr, is_hotfix=False)

        mock_url = get_mock_url()

        # Mock data
        mr_data = {
            "iid": 44,
            "project_id": 123,
            "title": "MR with Conflict",
            "state": "opened",
            "sha": "conflict123",
            "labels": ["merge_queue"],
            "source_branch": "feature/conflict",
            "target_branch": "main",
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "author": {"id": 1, "name": "Test User", "username": "testuser"},
            "web_url": "https://gitlab.com/test/project/-/merge_requests/44",
        }

        conflict_data = [
            {
                "old_path": "src/main.py",
                "new_path": "src/main.py",
                "sections": [
                    {
                        "head": "print('HEAD version')",
                        "origin": "print('origin version')",
                    }
                ],
            }
        ]

        # Setup matchers
        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/44")
        get_mr_response = jj.Response(status=200, json=mr_data)

        # Rebase returns 409 Conflict immediately
        rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/44/rebase")
        rebase_response = jj.Response(status=409, json={"message": "Merge conflict during rebase"})

        # Get conflicts endpoint
        conflicts_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/44/conflicts")
        conflicts_response = jj.Response(status=200, json=conflict_data)

        # Comment for conflict notification
        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/44/notes")
        comment_response = jj.Response(status=201, json={"id": 10, "body": "Conflict detected"})

        # GET notes - needed for _find_bot_comment
        get_notes_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/44/notes")
        get_notes_response = jj.Response(status=200, json=[])

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-webhook-secret",
        )

    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(rebase_matcher, rebase_response) as rebase_mock,
        mocked(conflicts_matcher, conflicts_response) as conflicts_mock,
        mocked(get_notes_matcher, get_notes_response),
        mocked(comment_matcher, comment_response) as comment_mock,
    ):
        with when("processor attempts to rebase MR"):
            gitlab_client = GitLabClient(settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
            processor = MergeProcessor(
                gitlab_client=gitlab_client,
                queue_manager=queue,
                notifier=notifier,
                settings=settings,
            )

            queue_item = await queue.get_next_mr()
            result = await processor._process_mr(queue_item)

        with then("MR is marked as failed due to conflict"):
            # Check processing result
            assert result == ProcessingResult.CONFLICT

            # Verify rebase was attempted
            rebase_history = await rebase_mock.fetch_history()
            assert len(rebase_history) == 1, "Rebase should have been attempted"

            # Verify conflicts were fetched
            conflicts_history = await conflicts_mock.fetch_history()
            assert len(conflicts_history) >= 1, "Conflicts should have been fetched"

            # Verify conflict comment was posted
            comment_history = await comment_mock.fetch_history()
            assert len(comment_history) >= 1, "Conflict comment should be posted"

            # Verify queue state
            mr_state = await queue.get_mr_state(44)
            assert mr_state["status"] == "failed", f"MR should be failed, got {mr_state}"


@scenario()
async def process_mr_with_conflict_during_rebase():
    """Test MR processing when conflict is discovered during rebase polling."""

    with given("MR starts rebase but conflict is discovered during polling"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        test_mr = MergeRequest(
            iid=45,
            title="MR with Async Conflict",
            state="opened",
            target_branch="main",
            source_branch="feature/async-conflict",
            sha="async456",
            labels=["merge_queue"],
            author=Author(id=1, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/45",
        )

        await queue.add_to_queue(test_mr, is_hotfix=False)

        mock_url = get_mock_url()

        mr_data = {
            "iid": 45,
            "project_id": 123,
            "title": "MR with Async Conflict",
            "state": "opened",
            "sha": "async456",
            "labels": ["merge_queue"],
            "source_branch": "feature/async-conflict",
            "target_branch": "main",
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "author": {"id": 1, "name": "Test User", "username": "testuser"},
            "web_url": "https://gitlab.com/test/project/-/merge_requests/45",
        }

        conflict_data = [
            {
                "old_path": "config.py",
                "new_path": "config.py",
            }
        ]

        # Setup matchers
        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/45")
        get_mr_response = jj.Response(status=200, json=mr_data)

        # Rebase starts successfully
        rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/45/rebase")
        rebase_response = jj.Response(status=202, json={"rebase_in_progress": True})

        # Status check returns conflict
        status_check_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/45")
        status_check_response = jj.Response(
            status=200,
            json={
                **mr_data,
                "rebase_in_progress": False,
                "has_conflicts": True,
            },
        )

        conflicts_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/45/conflicts")
        conflicts_response = jj.Response(status=200, json=conflict_data)

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/45/notes")
        comment_response = jj.Response(status=201, json={"id": 11})

        # GET notes - needed for _find_bot_comment
        get_notes_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/45/notes")
        get_notes_response = jj.Response(status=200, json=[])

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-webhook-secret",
            rebase_timeout_seconds=60,
        )

    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(rebase_matcher, rebase_response) as rebase_mock,
        mocked(status_check_matcher, status_check_response),
        mocked(conflicts_matcher, conflicts_response),
        mocked(get_notes_matcher, get_notes_response),
        mocked(comment_matcher, comment_response) as comment_mock,
    ):
        with when("processor polls rebase status and finds conflict"):
            gitlab_client = GitLabClient(settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
            processor = MergeProcessor(
                gitlab_client=gitlab_client,
                queue_manager=queue,
                notifier=notifier,
                settings=settings,
            )

            queue_item = await queue.get_next_mr()
            result = await processor._process_mr(queue_item)

        with then("MR is marked as failed after conflict discovery"):
            assert result == ProcessingResult.CONFLICT

            # Verify rebase was started
            rebase_history = await rebase_mock.fetch_history()
            assert len(rebase_history) == 1

            # Verify notification was sent
            comment_history = await comment_mock.fetch_history()
            assert len(comment_history) >= 1

            # Verify state
            mr_state = await queue.get_mr_state(45)
            assert mr_state["status"] == "failed"


@scenario()
async def process_mr_with_conflict_after_multiple_mrs():
    """Test conflict handling doesn't affect other MRs in queue."""

    with given("Multiple MRs in queue, one has conflict"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        # Add first MR (will have conflict)
        conflict_mr = MergeRequest(
            iid=46,
            title="Conflicting MR",
            state="opened",
            target_branch="main",
            source_branch="feature/conflict",
            sha="conflict789",
            labels=["merge_queue"],
            author=Author(id=1, name="User1", username="user1"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/46",
        )

        # Add second MR (should process fine after first fails)
        good_mr = MergeRequest(
            iid=47,
            title="Good MR",
            state="opened",
            target_branch="main",
            source_branch="feature/good",
            sha="good123",
            labels=["merge_queue"],
            author=Author(id=2, name="User2", username="user2"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/47",
        )

        await queue.add_to_queue(conflict_mr, is_hotfix=False)
        await queue.add_to_queue(good_mr, is_hotfix=False)

        mock_url = get_mock_url()

        # Mock data for conflicting MR
        conflict_mr_data = {
            "iid": 46,
            "project_id": 123,
            "title": "Conflicting MR",
            "state": "opened",
            "sha": "conflict789",
            "labels": ["merge_queue"],
            "source_branch": "feature/conflict",
            "target_branch": "main",
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "author": {"id": 1, "name": "User1", "username": "user1"},
            "web_url": "https://gitlab.com/test/project/-/merge_requests/46",
        }

        # Setup matchers for conflict MR
        get_mr_46_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/46")
        get_mr_46_response = jj.Response(status=200, json=conflict_mr_data)

        rebase_46_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/46/rebase")
        rebase_46_response = jj.Response(status=409, json={"message": "Conflict"})

        conflicts_46_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/46/conflicts")
        conflicts_46_response = jj.Response(status=200, json=[{"old_path": "file.py"}])

        comment_46_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/46/notes")
        comment_46_response = jj.Response(status=201, json={"id": 12})

        # GET notes - needed for _find_bot_comment
        get_notes_46_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/46/notes")
        get_notes_46_response = jj.Response(status=200, json=[])

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-webhook-secret",
        )

    async with (
        mocked(get_mr_46_matcher, get_mr_46_response),
        mocked(rebase_46_matcher, rebase_46_response) as rebase_mock,
        mocked(conflicts_46_matcher, conflicts_46_response),
        mocked(get_notes_46_matcher, get_notes_46_response),
        mocked(comment_46_matcher, comment_46_response),
    ):
        with when("first MR has conflict"):
            gitlab_client = GitLabClient(settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
            processor = MergeProcessor(
                gitlab_client=gitlab_client,
                queue_manager=queue,
                notifier=notifier,
                settings=settings,
            )

            # Process first MR
            first_item = await queue.get_next_mr()
            assert first_item.mr_iid == 46
            result = await processor._process_mr(first_item)

        with then("conflicting MR is failed but queue continues"):
            assert result == ProcessingResult.CONFLICT

            # Verify first MR is failed
            mr_46_state = await queue.get_mr_state(46)
            assert mr_46_state["status"] == "failed"

            # Verify second MR is still queued and ready
            next_item = await queue.get_next_mr()
            assert next_item is not None
            assert next_item.mr_iid == 47
            assert next_item.state == "queued"

            # Verify rebase was attempted
            rebase_history = await rebase_mock.fetch_history()
            assert len(rebase_history) == 1


__all__ = [
    "process_mr_with_conflict_after_multiple_mrs",
    "process_mr_with_conflict_during_rebase",
    "process_mr_with_immediate_conflict",
]
