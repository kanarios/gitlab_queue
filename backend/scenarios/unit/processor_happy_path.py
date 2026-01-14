"""Test scenario for successful MR processing flow.

This scenario tests the happy path where an MR is successfully:
1. Rebased
2. Tested (pipeline passes)
3. Merged

Uses JJ Remote Mock to simulate GitLab API responses.
"""

from __future__ import annotations

from datetime import UTC, datetime

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
async def process_mr_successfully():
    """Test successful MR processing from queue to merge."""

    with given("MR in queue and GitLab API mocked for success flow"):
        # Setup test database and queue
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        # Create test MR
        test_mr = MergeRequest(
            iid=42,
            title="Test MR",
            state="opened",
            target_branch="main",
            source_branch="feature/test",
            sha="abc123",
            labels=["merge_queue"],
            author=Author(id=1, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/42",
        )

        # Add MR to queue
        await queue.add_to_queue(test_mr, is_hotfix=False)

        # Setup JJ mocks for the full flow
        mock_url = get_mock_url()

        # Mock data
        mr_data = {
            "iid": 42,
            "project_id": 123,
            "title": "Test MR",
            "description": "Test description",
            "state": "opened",
            "target_branch": "main",
            "source_branch": "feature/test",
            "sha": "abc123",
            "labels": ["merge_queue"],
            "author": {"name": "Test User", "username": "testuser"},
            "web_url": "https://gitlab.com/test/project/-/merge_requests/42",
        }

        pipeline_data = {
            "id": 1001,
            "status": "success",
            "sha": "abc123",
            "ref": "feature/test",
            "web_url": "https://gitlab.com/test/project/-/pipelines/1001",
        }

        merged_mr_data = {
            **mr_data,
            "state": "merged",
            "merged_at": datetime.now(UTC).isoformat(),
        }

        # Setup matchers and responses
        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42")
        get_mr_response = jj.Response(status=200, json=mr_data)

        rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/rebase")
        rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        pipelines_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42/pipelines")
        pipelines_response = jj.Response(status=200, json=[pipeline_data])

        merge_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/merge")
        merge_response = jj.Response(status=200, json=merged_mr_data)

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/42/notes")
        comment_response = jj.Response(status=201, json={"id": 1, "body": "Processing started"})

        # Settings with mock URL
        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-webhook-secret",
            poll_interval_seconds=1,
            rebase_timeout_seconds=60,
            pipeline_timeout_seconds=300,
            pipeline_retry_count=2,
            stale_mr_warning_hours=24,
        )

    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(rebase_matcher, rebase_response),
        mocked(pipelines_matcher, pipelines_response),
        mocked(merge_matcher, merge_response) as merge_mock,
        mocked(comment_matcher, comment_response) as comment_mock,
    ):
        with when("processor runs one processing cycle"):
            # Create processor components
            gitlab_client = GitLabClient(settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, project_id=123)
            processor = MergeProcessor(
                gitlab_client=gitlab_client,
                queue_manager=queue,
                notifier=notifier,
                settings=settings,
            )

            # Process the MR
            queue_item = await queue.get_next_mr()
            assert queue_item is not None, "Queue should have an MR"

            result = await processor._process_mr(queue_item)

        with then("MR is successfully merged"):
            # Check processing result
            assert result == ProcessingResult.SUCCESS

            # Verify merge was called
            history = await merge_mock.fetch_history()
            assert len(history) == 1, "Merge should have been called once"

            # Verify queue state
            mr_state = await queue.get_mr_state(42)
            assert mr_state == "merged", f"MR should be merged, got {mr_state}"

            # Verify at least one comment was posted
            comment_history = await comment_mock.fetch_history()
            assert len(comment_history) >= 1, "At least one comment should be posted"

            # Verify queue is now empty
            next_item = await queue.get_next_mr()
            assert next_item is None, "Queue should be empty after processing"


@scenario()
async def process_mr_with_async_rebase():
    """Test MR processing with async rebase (rebase_in_progress=True)."""

    with given("MR in queue with async rebase scenario"):
        # Setup test database and queue
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        # Create test MR
        test_mr = MergeRequest(
            iid=43,
            title="Test MR with Async Rebase",
            state="opened",
            target_branch="main",
            source_branch="feature/async",
            sha="def456",
            labels=["merge_queue"],
            author=Author(id=1, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/43",
        )

        # Add MR to queue
        await queue.add_to_queue(test_mr, is_hotfix=False)

        mock_url = get_mock_url()

        # Mock data
        mr_data = {
            "iid": 43,
            "project_id": 123,
            "title": "Test MR with Async Rebase",
            "state": "opened",
            "sha": "def456",
            "labels": ["merge_queue"],
        }

        pipeline_data = {
            "id": 1002,
            "status": "success",
            "sha": "def456",
        }

        # Setup matchers - rebase will first return in_progress=True, then False
        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/43")
        get_mr_response = jj.Response(status=200, json=mr_data)

        # First rebase call initiates async rebase
        rebase_init_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/43/rebase")
        rebase_init_response = jj.Response(status=202, json={"rebase_in_progress": True})

        # Check rebase status - will be called to poll status
        # We'll return completed (rebase_in_progress=False)
        rebase_check_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/43")
        rebase_check_response = jj.Response(
            status=200, json={**mr_data, "rebase_in_progress": False}
        )

        pipelines_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/43/pipelines")
        pipelines_response = jj.Response(status=200, json=[pipeline_data])

        merge_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/43/merge")
        merge_response = jj.Response(status=200, json={**mr_data, "state": "merged"})

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/43/notes")
        comment_response = jj.Response(status=201, json={"id": 2})

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-webhook-secret",
            poll_interval_seconds=1,
            rebase_timeout_seconds=60,
        )

    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(rebase_init_matcher, rebase_init_response) as rebase_mock,
        mocked(rebase_check_matcher, rebase_check_response),
        mocked(pipelines_matcher, pipelines_response),
        mocked(merge_matcher, merge_response) as merge_mock,
        mocked(comment_matcher, comment_response),
    ):
        with when("processor handles async rebase"):
            gitlab_client = GitLabClient(settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, project_id=123)
            processor = MergeProcessor(
                gitlab_client=gitlab_client,
                queue_manager=queue,
                notifier=notifier,
                settings=settings,
            )

            queue_item = await queue.get_next_mr()
            result = await processor._process_mr(queue_item)

        with then("MR is successfully processed after async rebase"):
            assert result == ProcessingResult.SUCCESS

            # Verify rebase was initiated
            rebase_history = await rebase_mock.fetch_history()
            assert len(rebase_history) == 1, "Rebase should have been initiated"

            # Verify merge was called
            merge_history = await merge_mock.fetch_history()
            assert len(merge_history) == 1, "Merge should have been called"

            # Verify final state
            mr_state = await queue.get_mr_state(43)
            assert mr_state == "merged"


__all__ = [
    "process_mr_successfully",
    "process_mr_with_async_rebase",
]
