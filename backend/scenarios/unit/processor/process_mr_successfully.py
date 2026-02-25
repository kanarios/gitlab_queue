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
import vedro
from jj.mock import mocked
from scenarios.contexts.jj_gitlab_mock import get_mock_url

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.config import Settings
from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.processor import MergeProcessor, ProcessingResult
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.models.mr import Author, MergeRequest


class Scenario(vedro.Scenario):
    subject = "process mr successfully from queue to merge"

    async def given_mr_in_queue_and_gitlab_api_mocked(self):
        # Setup test database and queue
        self.db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await self.db.initialize()
        self.queue = QueueManager(self.db)
        await self.queue.ensure_schema()

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
        await self.queue.add_to_queue(test_mr, is_hotfix=False)

        # Setup JJ mocks for the full flow
        self.mock_url = get_mock_url()

        # Mock data
        self.mr_data = {
            "iid": 42,
            "project_id": 123,
            "title": "Test MR",
            "description": "Test description",
            "state": "opened",
            "target_branch": "main",
            "source_branch": "feature/test",
            "sha": "abc123",
            "labels": ["merge_queue"],
            "author": {"id": 1, "name": "Test User", "username": "testuser"},
            "web_url": "https://gitlab.com/test/project/-/merge_requests/42",
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
        }

        self.pipeline_data = {
            "id": 1001,
            "status": "success",
            "sha": "abc123",
            "ref": "feature/test",
            "web_url": "https://gitlab.com/test/project/-/pipelines/1001",
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
        self.pipelines_response = jj.Response(status=200, json=[self.pipeline_data])

        self.merge_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/merge")
        self.merge_response = jj.Response(status=200, json=self.merged_mr_data)

        self.comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/42/notes")
        self.comment_response = jj.Response(status=201, json={"id": 1, "body": "Processing started"})

        # GET notes - needed for _find_bot_comment
        self.get_notes_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42/notes")
        self.get_notes_response = jj.Response(status=200, json=[])

        # Settings with mock URL
        self.settings = Settings(
            gitlab_url=self.mock_url,
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

    async def when_processor_runs_one_processing_cycle(self):
        async with (
            mocked(self.get_mr_matcher, self.get_mr_response),
            mocked(self.rebase_matcher, self.rebase_response),
            mocked(self.pipelines_matcher, self.pipelines_response),
            mocked(self.merge_matcher, self.merge_response) as self.merge_mock,
            mocked(self.get_notes_matcher, self.get_notes_response),
            mocked(self.comment_matcher, self.comment_response) as self.comment_mock,
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
            self.comment_history = await self.comment_mock.fetch_history()

    async def then_mr_should_be_successfully_merged(self):
        # Check processing result
        assert self.result == ProcessingResult.SUCCESS

    async def and_merge_should_be_called_once(self):
        assert len(self.merge_history) == 1

    async def and_queue_state_should_be_merged(self):
        mr_state = await self.queue.get_mr_state(42)
        assert mr_state["status"] == "merged"

    async def and_at_least_one_comment_should_be_posted(self):
        assert len(self.comment_history) >= 1

    async def and_queue_should_be_empty_after_processing(self):
        next_item = await self.queue.get_next_mr()
        assert next_item is None
