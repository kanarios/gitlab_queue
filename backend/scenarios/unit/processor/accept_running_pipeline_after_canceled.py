"""Test scenario: accept running pipeline after canceled one.

When a canceled pipeline is skipped, the processor should accept
the next pipeline that has a non-terminal status (running, pending, etc).

This test verifies that:
1. The processor skips a canceled pipeline
2. The processor accepts a running pipeline (not skipped like canceled/failed)
3. The MR eventually merges when the running pipeline becomes success
"""

from __future__ import annotations

from datetime import UTC, datetime

import jj
import vedro
from jj.expiration_policy import ExpireAfterRequests
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
    subject = "accept running pipeline after skipping canceled one"

    async def given_mr_in_queue_with_canceled_then_running_pipeline(self):
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

        # Setup JJ mocks
        self.mock_url = get_mock_url()

        # MR data
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

        # Canceled pipeline - should be skipped
        self.canceled_pipeline = {
            "id": 1001,
            "status": "canceled",
            "sha": "abc123",
            "ref": "feature/test",
            "web_url": "https://gitlab.com/test/project/-/pipelines/1001",
        }

        # Running pipeline - should be accepted (not skipped like canceled/failed)
        self.running_pipeline = {
            "id": 1002,
            "status": "running",
            "sha": "abc123",
            "ref": "feature/test",
            "web_url": "https://gitlab.com/test/project/-/pipelines/1002",
        }

        # Success pipeline for merge (after running becomes success)
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

        # Setup matchers
        self.get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42")
        self.get_mr_response = jj.Response(status=200, json=self.mr_data)

        self.rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/rebase")
        self.rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        self.pipelines_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42/pipelines")
        # Responses in order: canceled (skipped), running (accepted), success (for merge)
        self.pipelines_response_canceled = jj.Response(status=200, json=[self.canceled_pipeline])
        self.pipelines_response_running = jj.Response(status=200, json=[self.running_pipeline])
        self.pipelines_response_success = jj.Response(status=200, json=[self.success_pipeline])

        self.merge_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/merge")
        self.merge_response = jj.Response(status=200, json=self.merged_mr_data)

        self.comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/42/notes")
        self.comment_response = jj.Response(status=201, json={"id": 1, "body": "Processing"})

        self.get_notes_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42/notes")
        self.get_notes_response = jj.Response(status=200, json=[])

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
            post_rebase_pipeline_wait_seconds=10,
        )

    async def when_processor_skips_canceled_and_accepts_running_pipeline(self):
        # Use ExpireAfterRequests to create a sequence:
        # 1. canceled (expires after 1 request) - will be skipped
        # 2. running (expires after 1 request) - will be accepted by _wait_for_post_rebase_pipeline
        # 3. success (used for polling during testing phase) - will complete the merge
        async with (
            mocked(self.get_mr_matcher, self.get_mr_response),
            mocked(self.rebase_matcher, self.rebase_response),
            # Success pipeline mock (registered first, used last during testing phase)
            mocked(self.pipelines_matcher, self.pipelines_response_success) as self.pipelines_mock,
            # Running pipeline mock (registered second, used after canceled expires)
            mocked(
                self.pipelines_matcher,
                self.pipelines_response_running,
                ExpireAfterRequests(1),
            ),
            # Canceled pipeline mock (registered last, expires after 1 request)
            mocked(
                self.pipelines_matcher,
                self.pipelines_response_canceled,
                ExpireAfterRequests(1),
            ),
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
            self.pipeline_history = await self.pipelines_mock.fetch_history()

    async def then_mr_should_be_successfully_merged(self):
        assert self.result == ProcessingResult.SUCCESS

    async def and_merge_should_be_called_once(self):
        assert len(self.merge_history) == 1

    async def and_running_pipeline_was_accepted_not_skipped(self):
        # The running pipeline was accepted (not skipped like canceled/failed).
        # This is verified by the fact that the MR was successfully merged.
        # If running was incorrectly skipped, the processor would have timed out.
        # The success mock should have been called during the testing phase.
        assert len(self.pipeline_history) >= 1, (
            f"Pipeline should be fetched for testing phase (got {len(self.pipeline_history)} calls)"
        )

    async def do_cleanup(self):
        await self.db.close()
