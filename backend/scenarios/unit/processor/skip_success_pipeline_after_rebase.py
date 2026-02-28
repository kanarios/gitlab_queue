"""Test scenario: skip success pipeline after rebase when SHA changes.

When SHA changes after rebase, the processor should skip pipelines with
success status that match the new SHA and wait for a new pipeline.

This test verifies that the processor correctly skips a stale success pipeline
(started before the rebase) and uses the next valid (running) pipeline.
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
    subject = "skip success pipeline after rebase when SHA changes"

    async def given_mr_in_queue_with_stale_success_then_running_pipeline(self):
        # Setup test database and queue
        """
        Set up an in-memory database, queue, test merge request, and HTTP mocks to simulate a post-rebase stale-success pipeline being skipped in favor of a running pipeline.

        Initializes an in-memory Database and QueueManager, enqueues a merge request with a pre-rebase SHA, constructs MR payloads for pre- and post-rebase states, defines pipeline fixtures (stale success, running, final success), prepares JJ HTTP matchers and responses for MR, rebase, pipelines, merge and notes endpoints, and builds Settings used by the processor. Populates instance attributes used by the scenario: db, queue, mock_url, mr_data_old, mr_data_new, stale_success_pipeline, running_pipeline, final_success_pipeline, merged_mr_data, get_mr_matcher, get_mr_response_new, get_mr_response_old, rebase_matcher, rebase_response, pipelines_matcher, pipelines_response_stale, pipelines_response_running, pipelines_response_final, merge_matcher, merge_response, comment_matcher, comment_response, get_notes_matcher, get_notes_response, and settings.
        """
        self.db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await self.db.initialize()
        self.queue = QueueManager(self.db)
        await self.queue.ensure_schema()

        # Create test MR with old SHA
        test_mr = MergeRequest(
            iid=42,
            title="Test MR with stale success pipeline after rebase",
            state="opened",
            target_branch="main",
            source_branch="feature/test",
            sha="old_sha_123",  # Old SHA before rebase
            labels=["merge_queue"],
            author=Author(id=1, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/42",
        )

        # Add MR to queue
        await self.queue.add_to_queue(test_mr, is_hotfix=False)

        # Setup JJ mocks
        self.mock_url = get_mock_url()

        # Common MR fields
        mr_common = {
            "iid": 42,
            "project_id": 123,
            "title": "Test MR with stale success pipeline after rebase",
            "description": "Test description",
            "state": "opened",
            "target_branch": "main",
            "source_branch": "feature/test",
            "labels": ["merge_queue"],
            "author": {"id": 1, "name": "Test User", "username": "testuser"},
            "web_url": "https://gitlab.com/test/project/-/merge_requests/42",
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
        }

        # MR data before rebase - old SHA (used for initial fetch + pre-rebase SHA capture)
        self.mr_data_old = {**mr_common, "sha": "old_sha_123"}

        # MR data after rebase - new SHA
        self.mr_data_new = {**mr_common, "sha": "new_sha_456"}

        # Stale success pipeline with new SHA - should be skipped
        self.stale_success_pipeline = {
            "id": 1001,
            "status": "success",
            "sha": "new_sha_456",
            "ref": "feature/test",
            "web_url": "https://gitlab.com/test/project/-/pipelines/1001",
        }

        # Running pipeline with new SHA - should be accepted after stale is skipped
        self.running_pipeline = {
            "id": 1002,
            "status": "running",
            "sha": "new_sha_456",
            "ref": "feature/test",
            "web_url": "https://gitlab.com/test/project/-/pipelines/1002",
        }

        # Final success pipeline for merge
        self.final_success_pipeline = {
            "id": 1002,
            "status": "success",
            "sha": "new_sha_456",
            "ref": "feature/test",
            "web_url": "https://gitlab.com/test/project/-/pipelines/1002",
        }

        self.merged_mr_data = {
            **self.mr_data_new,
            "state": "merged",
            "merged_at": datetime.now(UTC).isoformat(),
        }

        # Setup matchers
        self.get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42")
        # Default response: new SHA (post-rebase)
        self.get_mr_response_new = jj.Response(status=200, json=self.mr_data_new)
        # Old SHA response expires after 2 requests:
        #   1st call: initial MR fetch in _process_mr
        #   2nd call: _capture_pre_rebase_sha
        # After that, new SHA is returned for check_rebase_status and _wait_for_post_rebase_pipeline
        self.get_mr_response_old = jj.Response(status=200, json=self.mr_data_old)

        self.rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/rebase")
        self.rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        self.pipelines_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42/pipelines")
        # First response: stale success pipeline (expires after 1 request)
        self.pipelines_response_stale = jj.Response(status=200, json=[self.stale_success_pipeline])
        # Second response: running pipeline (expires after 1 request)
        self.pipelines_response_running = jj.Response(status=200, json=[self.running_pipeline])
        # Third response: final success pipeline (used for merge check)
        self.pipelines_response_final = jj.Response(status=200, json=[self.final_success_pipeline])

        self.merge_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/merge")
        self.merge_response = jj.Response(status=200, json=self.merged_mr_data)

        self.comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/42/notes")
        self.comment_response = jj.Response(status=201, json={"id": 1, "body": "Processing"})

        self.get_notes_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42/notes")
        self.get_notes_response = jj.Response(status=200, json=[])

        self.project_matcher = jj.match("GET", "/api/v4/projects/123")
        self.project_response = jj.Response(status=200, json={"id": 123, "web_url": f"{self.mock_url}/test/project"})

        # Settings
        self.settings = Settings(
            gitlab_url=self.mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-webhook-secret",
            poll_interval_seconds=0.1,
            rebase_timeout_seconds=60,
            pipeline_timeout_seconds=300,
            pipeline_retry_count=2,
            stale_mr_warning_hours=24,
            post_rebase_pipeline_wait_seconds=5,
        )

    async def when_processor_skips_stale_success_and_uses_running_pipeline(self):
        """
        Execute the merge processor against a mocked GitLab scenario where a stale successful pipeline (tied to a pre-rebase SHA) is skipped and a running pipeline for the post-rebase SHA is used to complete the merge.

        Sets up HTTP mocks for MR fetches (pre- and post-rebase), rebase, pipelines (stale success, running, final success), merge, and notes; constructs GitLabClient, MRNotifier, and MergeProcessor; processes the next queued MR; and records results and fetch histories for assertions:
        - self.result: the ProcessingResult returned by the processor
        - self.merge_history: fetch history of the merge call mock
        - self.pipeline_stale_history: fetch history of the stale pipeline mock
        - self.pipeline_running_history: fetch history of the running pipeline mock
        """
        async with (
            mocked(self.project_matcher, self.project_response),
            # Default MR response: new SHA (registered first, used after old expires)
            mocked(self.get_mr_matcher, self.get_mr_response_new),
            # Old SHA MR response: expires after 2 requests (initial fetch + pre-rebase SHA)
            mocked(
                self.get_mr_matcher,
                self.get_mr_response_old,
                ExpireAfterRequests(2),
            ),
            mocked(self.rebase_matcher, self.rebase_response),
            # Final success pipeline mock (registered first, used last)
            mocked(self.pipelines_matcher, self.pipelines_response_final) as self.pipelines_final_mock,
            # Running pipeline mock (registered second, expires after 1 request)
            mocked(
                self.pipelines_matcher,
                self.pipelines_response_running,
                ExpireAfterRequests(1),
            ) as self.pipelines_running_mock,
            # Stale success pipeline mock (registered last, expires after 1 request)
            mocked(
                self.pipelines_matcher,
                self.pipelines_response_stale,
                ExpireAfterRequests(1),
            ) as self.pipelines_stale_mock,
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

            # Fetch history
            self.merge_history = await self.merge_mock.fetch_history()
            self.pipeline_stale_history = await self.pipelines_stale_mock.fetch_history()
            self.pipeline_running_history = await self.pipelines_running_mock.fetch_history()

    async def then_mr_should_be_successfully_merged(self):
        """
        Assert that the merge request was processed and merged successfully.

        Raises:
            AssertionError: If the processor result is not `ProcessingResult.SUCCESS`.
        """
        assert self.result == ProcessingResult.SUCCESS

    async def and_merge_should_be_called_once(self):
        """
        Assert that the merge API was called exactly once.

        Raises:
            AssertionError: If the recorded merge call count is not exactly 1.
        """
        assert len(self.merge_history) == 1

    async def and_stale_success_pipeline_was_fetched_once(self):
        # Verify stale success pipeline mock was called (the skip happened)
        """
        Assert that the stale success pipeline was fetched exactly once.

        Raises:
            AssertionError: If the stale pipeline fetch count is not 1.
        """
        assert len(self.pipeline_stale_history) == 1, (
            f"Stale success pipeline mock should be called exactly once (got {len(self.pipeline_stale_history)})"
        )

    async def and_running_pipeline_was_used_once(self):
        # Verify running pipeline mock was called after stale was skipped
        """
        Asserts that the running pipeline mock was invoked exactly once after the stale pipeline was skipped.

        Raises:
            AssertionError: If the running pipeline mock was not called exactly once.
        """
        assert len(self.pipeline_running_history) == 1, (
            f"Running pipeline mock should be called exactly once (got {len(self.pipeline_running_history)})"
        )

    async def do_cleanup(self):
        """
        Close the scenario's database connection.

        Await the asynchronous close operation on self.db to release resources used by the in-memory test database.
        """
        await self.db.close()
