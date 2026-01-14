"""Simple test scenarios for successful MR processing.

This scenario tests the happy path where an MR is successfully processed.
Uses JJ Remote Mock to simulate GitLab API responses.
"""

from __future__ import annotations

import jj
import vedro
from jj.mock import mocked
from scenarios.contexts.jj_gitlab_mock import get_mock_url
from scenarios.contexts.sqlite_client import test_database

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.config import Settings
from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.processor import MergeProcessor, ProcessingResult
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.models.mr import Author, MergeRequest


class ProcessMRSuccessfully(vedro.Scenario):
    """Test successful MR processing from queue to merge."""

    subject = "processor: happy path processing"

    def __init__(self):
        self.db = None
        self.queue = None
        self._db_context = None

    async def given_mr_in_queue_and_api_mocked(self):
        """Setup MR in queue and GitLab API mocks."""
        # Setup test database
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        # Create test MR
        self.test_mr = MergeRequest(
            iid=42,
            title="Test MR",
            state="opened",
            target_branch="main",
            source_branch="feature/test",
            sha="abc123",
            labels=["merge_queue"],
            author=Author(id=42, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/42",
        )

        # Add MR to queue
        await self.queue.add_to_queue(self.test_mr, is_hotfix=False)

        # Mock data
        self.mr_data = {
            "iid": 42,
            "project_id": 123,
            "title": "Test MR",
            "state": "opened",
            "sha": "abc123",
            "labels": ["merge_queue"],
        }

        self.pipeline_data = {
            "id": 1001,
            "status": "success",
            "sha": "abc123",
        }

        # Settings
        self.settings = Settings(
            gitlab_url=get_mock_url(),
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            db_path=":memory:",
            poll_interval_seconds=0.1,
            rebase_timeout_seconds=60,
            pipeline_timeout_seconds=300,
        )

    async def when_processor_processes_mr(self):
        """Process the MR through the processor."""
        # Setup mocks
        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42")
        get_mr_response = jj.Response(status=200, json=self.mr_data)

        rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/rebase")
        rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        pipelines_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42/pipelines")
        pipelines_response = jj.Response(status=200, json=[self.pipeline_data])

        merge_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/merge")
        merge_response = jj.Response(status=200, json={**self.mr_data, "state": "merged"})

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/42/notes")
        comment_response = jj.Response(status=201, json={"id": 1})

        async with (
            mocked(get_mr_matcher, get_mr_response),
            mocked(rebase_matcher, rebase_response) as self.rebase_mock,
            mocked(pipelines_matcher, pipelines_response),
            mocked(merge_matcher, merge_response) as self.merge_mock,
            mocked(comment_matcher, comment_response) as self.comment_mock,
        ):
            # Create processor
            gitlab_client = GitLabClient(self.settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, project_id=123)
            processor = MergeProcessor(
                gitlab_client=gitlab_client,
                queue_manager=self.queue,
                notifier=notifier,
                settings=self.settings,
            )

            # Process the MR
            queue_item = await self.queue.get_next_mr()
            assert queue_item is not None, "Queue should have an MR"

            self.result = await processor._process_mr(queue_item)

    async def then_mr_is_successfully_merged(self):
        """Verify MR was successfully processed and merged."""
        # Check processing result
        assert self.result == ProcessingResult.SUCCESS

        # Verify merge was called
        history = await self.merge_mock.fetch_history()
        assert len(history) == 1, "Merge should have been called once"

        # Verify queue state
        mr_state = await self.queue.get_mr_state(42)
        assert mr_state == "merged", f"MR should be merged, got {mr_state}"

        # Verify at least one comment was posted
        comment_history = await self.comment_mock.fetch_history()
        assert len(comment_history) >= 1, "At least one comment should be posted"

    async def cleanup(self):
        """Clean up test resources."""
        if self._db_context:
            await self._db_context.__aexit__(None, None, None)
