"""Simple test scenarios for successful MR processing.

This scenario tests the happy path where an MR is successfully processed.
Uses JJ Remote Mock to simulate GitLab API responses.
"""

from __future__ import annotations

import jj
import vedro
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
    subject = "processor: happy path processing"

    def __init__(self):
        self.db = None
        self.queue = None
        self._db_context = None

    async def given_mr_in_queue_and_api_mocked(self):
        # Setup test database
        self.db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await self.db.initialize()
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
            "source_branch": "feature/test",
            "target_branch": "main",
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "author": {"id": 42, "name": "Test User", "username": "testuser"},
            "web_url": "https://gitlab.com/test/project/-/merge_requests/42",
        }

        self.pipeline_data = {
            "id": 1001,
            "status": "success",
            "sha": "abc123",
        }

        # Settings
        self.mock_url = get_mock_url()
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
        )

    async def when_processor_processes_mr(self):
        # Setup mocks
        """
        Sets up HTTP mocks for GitLab API endpoints, runs the merge processor against the queued merge request, and records the outcome.

        This method configures mock responses for fetching the MR, triggering a rebase, listing pipelines, performing the merge, reading notes, and posting a comment. It constructs the GitLab client, notifier, and MergeProcessor, retrieves the next MR from the queue, asserts an item was retrieved, invokes the processor on that item, and stores the processing result along with the recorded merge and comment mock histories on the test instance (self.result, self.merge_history, self.comment_history).
        """
        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42")
        get_mr_response = jj.Response(status=200, json=self.mr_data)

        rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/rebase")
        rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        pipelines_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42/pipelines")
        pipelines_response = jj.Response(status=200, json=[self.pipeline_data])

        merge_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/merge")
        merge_response = jj.Response(status=200, json={**self.mr_data, "state": "merged"})

        # GET notes - needed for _find_bot_comment
        get_notes_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42/notes")
        get_notes_response = jj.Response(status=200, json=[])

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/42/notes")
        comment_response = jj.Response(status=201, json={"id": 1, "body": "test"})

        project_matcher = jj.match("GET", "/api/v4/projects/123")
        project_response = jj.Response(status=200, json={"id": 123, "web_url": f"{self.mock_url}/test/project"})

        async with (
            mocked(project_matcher, project_response),
            mocked(get_mr_matcher, get_mr_response),
            mocked(rebase_matcher, rebase_response) as self.rebase_mock,
            mocked(pipelines_matcher, pipelines_response),
            mocked(merge_matcher, merge_response) as self.merge_mock,
            mocked(get_notes_matcher, get_notes_response),
            mocked(comment_matcher, comment_response) as self.comment_mock,
        ):
            # Create processor
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

            # Capture mock histories before exiting context
            self.merge_history = await self.merge_mock.fetch_history()
            self.comment_history = await self.comment_mock.fetch_history()

    async def then_mr_is_successfully_merged(self):
        # Check processing result
        """
        Assert that the merge request was processed and merged successfully.

        Checks that processing result is SUCCESS, exactly one merge operation was invoked,
        the MR's queue state is "merged" for IID 42, and at least one comment was posted.
        """
        assert self.result == ProcessingResult.SUCCESS

        # Verify merge was called
        assert len(self.merge_history) == 1

        # Verify queue state
        mr_state = await self.queue.get_mr_state(42)
        assert mr_state["status"] == "merged"

        # Verify at least one comment was posted
        assert len(self.comment_history) >= 1

    async def cleanup(self):
        """
        Close the database connection if it has been initialized.

        If the Scenario instance holds an open database in `self.db`, close it; otherwise do nothing.
        """
        if self.db:
            await self.db.close()
