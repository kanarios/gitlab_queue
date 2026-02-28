"""Test scenario: skip canceled pipeline in fast-forward rebase case.

When SHA doesn't change after rebase (fast-forward), the processor should
skip pipelines with canceled/failed status and wait for a new pipeline.

This test verifies that the processor correctly skips a canceled pipeline
and uses the next valid (success) pipeline for the merge.
"""

from __future__ import annotations

from datetime import UTC, datetime

import jj
import vedro
from jj.expiration_policy import ExpireAfterRequests
from jj.mock import mocked

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.config import Settings
from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.processor import MergeProcessor, ProcessingResult
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.models.mr import Author, MergeRequest
from scenarios.contexts.jj_gitlab_mock import get_mock_url


class Scenario(vedro.Scenario):
    subject = "skip canceled pipeline in fast-forward rebase case"

    async def given_mr_in_queue_with_canceled_then_success_pipeline(self):
        # Setup test database and queue
        self.db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await self.db.initialize()
        self.queue = QueueManager(self.db)
        await self.queue.ensure_schema()

        # Create test MR
        test_mr = MergeRequest(
            iid=42,
            title="Test MR with canceled pipeline",
            state="opened",
            target_branch="main",
            source_branch="feature/test",
            sha="abc123",  # Same SHA before and after rebase (fast-forward)
            labels=["merge_queue"],
            author=Author(id=1, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/42",
        )

        # Add MR to queue
        await self.queue.add_to_queue(test_mr, is_hotfix=False)

        # Setup JJ mocks
        self.mock_url = get_mock_url()

        # MR data - SHA stays the same (fast-forward case)
        self.mr_data = {
            "iid": 42,
            "project_id": 123,
            "title": "Test MR with canceled pipeline",
            "description": "Test description",
            "state": "opened",
            "target_branch": "main",
            "source_branch": "feature/test",
            "sha": "abc123",  # Same SHA
            "labels": ["merge_queue"],
            "author": {"id": 1, "name": "Test User", "username": "testuser"},
            "web_url": "https://gitlab.com/test/project/-/merge_requests/42",
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
        }

        # Canceled pipeline - should be skipped
        self.canceled_pipeline = {
            "id": 1001,
            "status": "canceled",
            "sha": "abc123",
            "ref": "feature/test",
            "web_url": "https://gitlab.com/test/project/-/pipelines/1001",
        }

        # Success pipeline - should be used after canceled is skipped
        self.success_pipeline = {
            "id": 1002,
            "status": "success",
            "sha": "abc123",
            "ref": "feature/test",
            "web_url": "https://gitlab.com/test/project/-/pipelines/1002",
        }

        self.merged_mr_data = {
            **self.mr_data,
            "state": "merged",
            "merged_at": datetime.now(UTC).isoformat(),
        }

        # Setup matchers and responses
        self.get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42")
        self.get_mr_response = jj.Response(status=200, json=self.mr_data)

        self.rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/rebase")
        self.rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        self.pipelines_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42/pipelines")
        # First response: canceled pipeline (expires after 1 request)
        self.pipelines_response_canceled = jj.Response(status=200, json=[self.canceled_pipeline])
        # Second response: success pipeline (used after canceled expires)
        self.pipelines_response_success = jj.Response(status=200, json=[self.success_pipeline])

        self.merge_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/merge")
        self.merge_response = jj.Response(status=200, json=self.merged_mr_data)

        self.comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/42/notes")
        self.comment_response = jj.Response(status=201, json={"id": 1, "body": "Processing"})

        self.get_notes_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42/notes")
        self.get_notes_response = jj.Response(status=200, json=[])

        self.project_matcher = jj.match("GET", "/api/v4/projects/123")
        self.project_response = jj.Response(status=200, json={"id": 123, "web_url": f"{self.mock_url}/test/project"})

        # Settings with mock URL and short timeout
        self.settings = Settings(
            gitlab_url=self.mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-webhook-secret",
            poll_interval_seconds=0.1,  # Fast polling for tests
            rebase_timeout_seconds=60,
            pipeline_timeout_seconds=300,
            pipeline_retry_count=2,
            stale_mr_warning_hours=24,
            post_rebase_pipeline_wait_seconds=5,  # Short timeout for test
        )

    async def when_processor_skips_canceled_and_uses_success_pipeline(self):
        # Use ExpireAfterRequests to create a sequence:
        # First call returns canceled (then expires), subsequent calls return success
        """
        Set up mocks where the first pipeline query is canceled and subsequent queries are successful, then process the queued merge request and record outcomes.

        Configures mocked responses so the pipelines endpoint first returns a canceled pipeline (then expires) and thereafter returns a successful pipeline; instantiates GitLab client, notifier, and MergeProcessor; retrieves the next MR from the queue and processes it; and saves the processing result plus merge and pipeline fetch histories on `self` for later assertions.
        """
        async with (
            mocked(self.project_matcher, self.project_response),
            mocked(self.get_mr_matcher, self.get_mr_response),
            mocked(self.rebase_matcher, self.rebase_response),
            # Success pipeline mock (registered first, used after canceled expires)
            mocked(self.pipelines_matcher, self.pipelines_response_success) as self.pipelines_success_mock,
            # Canceled pipeline mock (registered last, expires after 1 request)
            mocked(
                self.pipelines_matcher,
                self.pipelines_response_canceled,
                ExpireAfterRequests(1),
            ) as self.pipelines_canceled_mock,
            mocked(self.merge_matcher, self.merge_response) as self.merge_mock,
            mocked(self.get_notes_matcher, self.get_notes_response),
            mocked(self.comment_matcher, self.comment_response),
        ):
            # Create processor components
            gitlab_client = GitLabClient(self.settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, settings=self.settings)
            processor = MergeProcessor(
                gitlab_client=gitlab_client,
                queue_manager=self.queue,
                notifier=notifier,
                settings=self.settings,
            )

            # Process the MR
            queue_item = await self.queue.get_next_mr()
            assert queue_item is not None

            self.result = await processor._process_mr(queue_item)

            # Fetch history while still in mock context
            self.merge_history = await self.merge_mock.fetch_history()
            self.pipeline_canceled_history = await self.pipelines_canceled_mock.fetch_history()
            self.pipeline_success_history = await self.pipelines_success_mock.fetch_history()

    async def then_mr_should_be_successfully_merged(self):
        """
        Assert that the processed merge request was merged successfully.

        Raises:
            AssertionError: If the processing result is not ProcessingResult.SUCCESS.
        """
        assert self.result == ProcessingResult.SUCCESS

    async def and_merge_should_be_called_once(self):
        """
        Assert that exactly one merge operation was invoked during the test scenario.

        This verifies that the recorded merge history contains a single entry.
        """
        assert len(self.merge_history) == 1

    async def and_canceled_pipeline_was_fetched_first(self):
        # Verify canceled pipeline mock was called (the skip happened)
        """
        Asserts that the canceled pipeline was fetched exactly once.

        Raises:
            AssertionError: If the canceled pipeline fetch count is not exactly one.
        """
        assert len(self.pipeline_canceled_history) == 1, (
            f"Canceled pipeline mock should be called exactly once (got {len(self.pipeline_canceled_history)})"
        )

    async def and_success_pipeline_was_used_after_skip(self):
        # Verify success pipeline mock was called after canceled was skipped
        """
        Verify that the mock for the successful pipeline was invoked at least once after the canceled pipeline was skipped.

        Raises:
            AssertionError: If the success pipeline mock was not called (fewer than 1 calls).
        """
        assert len(self.pipeline_success_history) >= 1, (
            f"Success pipeline mock should be called after canceled was skipped (got {len(self.pipeline_success_history)})"
        )

    async def do_cleanup(self):
        """
        Close the scenario's database connection.

        Closes the underlying asynchronous database client used by the scenario to release resources before test teardown.
        """
        await self.db.close()
