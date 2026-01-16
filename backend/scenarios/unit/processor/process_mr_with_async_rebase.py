"""Test scenario for MR processing with async rebase.

This scenario tests the case where rebase returns rebase_in_progress=True,
requiring the processor to poll for completion.
"""

from __future__ import annotations

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
    subject = "process mr with async rebase"

    async def given_mr_in_queue_with_async_rebase_scenario(self):
        # Setup test database and queue
        self.db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await self.db.initialize()
        self.queue = QueueManager(self.db)
        await self.queue.ensure_schema()

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
        await self.queue.add_to_queue(test_mr, is_hotfix=False)

        self.mock_url = get_mock_url()

        # Mock data
        self.mr_data = {
            "iid": 43,
            "project_id": 123,
            "title": "Test MR with Async Rebase",
            "state": "opened",
            "sha": "def456",
            "labels": ["merge_queue"],
            "source_branch": "feature/async",
            "target_branch": "main",
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "author": {"id": 1, "name": "Test User", "username": "testuser"},
            "web_url": "https://gitlab.com/test/project/-/merge_requests/43",
        }

        self.pipeline_data = {
            "id": 1002,
            "status": "success",
            "sha": "def456",
        }

        # Setup matchers - rebase will first return in_progress=True, then False
        self.get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/43")
        self.get_mr_response = jj.Response(status=200, json=self.mr_data)

        # First rebase call initiates async rebase
        self.rebase_init_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/43/rebase")
        self.rebase_init_response = jj.Response(status=202, json={"rebase_in_progress": True})

        # Check rebase status - will be called to poll status
        # We'll return completed (rebase_in_progress=False)
        self.rebase_check_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/43")
        self.rebase_check_response = jj.Response(status=200, json={**self.mr_data, "rebase_in_progress": False})

        self.pipelines_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/43/pipelines")
        self.pipelines_response = jj.Response(status=200, json=[self.pipeline_data])

        self.merge_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/43/merge")
        self.merge_response = jj.Response(status=200, json={**self.mr_data, "state": "merged"})

        self.comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/43/notes")
        self.comment_response = jj.Response(status=201, json={"id": 2})

        # GET notes - needed for _find_bot_comment
        self.get_notes_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/43/notes")
        self.get_notes_response = jj.Response(status=200, json=[])

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
        )

    async def when_processor_handles_async_rebase(self):
        async with (
            mocked(self.get_mr_matcher, self.get_mr_response),
            mocked(self.rebase_init_matcher, self.rebase_init_response) as self.rebase_mock,
            mocked(self.rebase_check_matcher, self.rebase_check_response),
            mocked(self.pipelines_matcher, self.pipelines_response),
            mocked(self.merge_matcher, self.merge_response) as self.merge_mock,
            mocked(self.get_notes_matcher, self.get_notes_response),
            mocked(self.comment_matcher, self.comment_response),
        ):
            gitlab_client = GitLabClient(self.settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, settings=self.settings)
            processor = MergeProcessor(
                gitlab_client=gitlab_client,
                queue_manager=self.queue,
                notifier=notifier,
                settings=self.settings,
            )

            queue_item = await self.queue.get_next_mr()
            self.result = await processor._process_mr(queue_item)

            # Fetch history while still in mock context
            self.rebase_history = await self.rebase_mock.fetch_history()
            self.merge_history = await self.merge_mock.fetch_history()

    async def then_mr_should_be_successfully_processed(self):
        assert self.result == ProcessingResult.SUCCESS

    async def and_rebase_should_be_initiated(self):
        assert len(self.rebase_history) == 1, "Rebase should have been initiated"

    async def and_merge_should_be_called(self):
        assert len(self.merge_history) == 1, "Merge should have been called"

    async def and_final_state_should_be_merged(self):
        mr_state = await self.queue.get_mr_state(43)
        assert mr_state["status"] == "merged"
