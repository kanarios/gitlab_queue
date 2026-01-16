"""Test scenarios for processor handling non-actionable pipeline statuses.

This scenario tests how the processor handles pipeline statuses that require
manual intervention and cannot be automatically retried:
- manual (waiting for manual action)
- skipped (pipeline was skipped)
- blocked (blocked by another pipeline)
- waiting_for_resource (waiting for runner)

These statuses should immediately fail the MR instead of looping indefinitely.
"""

from __future__ import annotations

import jj
from jj.mock import mocked
from scenarios.contexts.jj_gitlab_mock import get_mock_url
from vedro import given, params, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.config import Settings
from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.processor import MergeProcessor, ProcessingResult
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.models.mr import Author, MergeRequest


@scenario(
    [
        params("manual"),
        params("skipped"),
        params("blocked"),
        params("waiting_for_resource"),
    ]
)
async def process_mr_with_non_actionable_pipeline_status(status: str):
    """Test MR processing when pipeline is in non-actionable state."""

    with given(f"MR with pipeline in '{status}' status"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        mr_iid = 100

        test_mr = MergeRequest(
            iid=mr_iid,
            title=f"MR with {status} Pipeline",
            state="opened",
            target_branch="main",
            source_branch=f"feature/{status}-pipeline",
            sha=f"{status}123",
            labels=["merge_queue"],
            author=Author(id=1, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url=f"https://gitlab.com/test/project/-/merge_requests/{mr_iid}",
        )

        await queue.add_to_queue(test_mr, is_hotfix=False)

        mock_url = get_mock_url()

        mr_data = {
            "iid": mr_iid,
            "project_id": 123,
            "title": f"MR with {status} Pipeline",
            "state": "opened",
            "sha": f"{status}123",
            "labels": ["merge_queue"],
            "source_branch": f"feature/{status}-pipeline",
            "target_branch": "main",
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "author": {"id": 1, "name": "Test User", "username": "testuser"},
            "web_url": f"https://gitlab.com/test/project/-/merge_requests/{mr_iid}",
        }

        # Pipeline in non-actionable state
        non_actionable_pipeline = {
            "id": 9001,
            "status": status,
            "sha": f"{status}123",
            "web_url": "https://gitlab.com/test/project/-/pipelines/9001",
        }

        get_mr_matcher = jj.match("GET", f"/api/v4/projects/123/merge_requests/{mr_iid}")
        get_mr_response = jj.Response(status=200, json=mr_data)

        rebase_matcher = jj.match("PUT", f"/api/v4/projects/123/merge_requests/{mr_iid}/rebase")
        rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        pipelines_matcher = jj.match("GET", f"/api/v4/projects/123/merge_requests/{mr_iid}/pipelines")
        pipelines_response = jj.Response(status=200, json=[non_actionable_pipeline])

        comment_matcher = jj.match("POST", f"/api/v4/projects/123/merge_requests/{mr_iid}/notes")
        comment_response = jj.Response(status=201, json={"id": 30})

        get_notes_matcher = jj.match("GET", f"/api/v4/projects/123/merge_requests/{mr_iid}/notes")
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
            pipeline_retry_count=3,  # Even with retries, non-actionable should fail immediately
            poll_interval_seconds=0.1,
            pipeline_timeout_seconds=60,
        )

    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(rebase_matcher, rebase_response),
        mocked(pipelines_matcher, pipelines_response),
        mocked(get_notes_matcher, get_notes_response),
        mocked(comment_matcher, comment_response) as comment_mock,
    ):
        with when(f"processor encounters pipeline in '{status}' state"):
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

        with then("MR is immediately marked as failed"):
            assert result == ProcessingResult.PIPELINE_FAILED, (
                f"Expected PIPELINE_FAILED for '{status}' status, got {result}"
            )

        with then("failure comment was posted"):
            comment_history = await comment_mock.fetch_history()
            assert len(comment_history) >= 1, "Failure comment should be posted"

        with then("MR state is failed in database"):
            mr_state = await queue.get_mr_state(mr_iid)
            assert mr_state["status"] == "failed", f"MR should be failed, got {mr_state['status']}"


@scenario()
async def non_actionable_status_does_not_retry():
    """Test that non-actionable status fails immediately without retry attempts."""

    with given("MR with manual pipeline and retry count configured"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        mr_iid = 101

        test_mr = MergeRequest(
            iid=mr_iid,
            title="MR with Manual Pipeline",
            state="opened",
            target_branch="main",
            source_branch="feature/manual-no-retry",
            sha="manual456",
            labels=["merge_queue"],
            author=Author(id=1, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url=f"https://gitlab.com/test/project/-/merge_requests/{mr_iid}",
        )

        await queue.add_to_queue(test_mr, is_hotfix=False)

        mock_url = get_mock_url()

        mr_data = {
            "iid": mr_iid,
            "project_id": 123,
            "title": "MR with Manual Pipeline",
            "state": "opened",
            "sha": "manual456",
            "labels": ["merge_queue"],
            "source_branch": "feature/manual-no-retry",
            "target_branch": "main",
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "author": {"id": 1, "name": "Test User", "username": "testuser"},
            "web_url": f"https://gitlab.com/test/project/-/merge_requests/{mr_iid}",
        }

        manual_pipeline = {
            "id": 9002,
            "status": "manual",
            "sha": "manual456",
        }

        get_mr_matcher = jj.match("GET", f"/api/v4/projects/123/merge_requests/{mr_iid}")
        get_mr_response = jj.Response(status=200, json=mr_data)

        rebase_matcher = jj.match("PUT", f"/api/v4/projects/123/merge_requests/{mr_iid}/rebase")
        rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        pipelines_matcher = jj.match("GET", f"/api/v4/projects/123/merge_requests/{mr_iid}/pipelines")
        pipelines_response = jj.Response(status=200, json=[manual_pipeline])

        comment_matcher = jj.match("POST", f"/api/v4/projects/123/merge_requests/{mr_iid}/notes")
        comment_response = jj.Response(status=201, json={"id": 31})

        get_notes_matcher = jj.match("GET", f"/api/v4/projects/123/merge_requests/{mr_iid}/notes")
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
            pipeline_retry_count=5,  # High retry count - should NOT be used
            poll_interval_seconds=0.1,
            pipeline_timeout_seconds=60,
        )

    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(rebase_matcher, rebase_response) as rebase_mock,
        mocked(pipelines_matcher, pipelines_response) as pipelines_mock,
        mocked(get_notes_matcher, get_notes_response),
        mocked(comment_matcher, comment_response),
    ):
        with when("processor encounters manual pipeline"):
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

        with then("MR fails without retry"):
            assert result == ProcessingResult.PIPELINE_FAILED

        with then("rebase was only called once (initial rebase, no retry)"):
            rebase_history = await rebase_mock.fetch_history()
            assert len(rebase_history) == 1, f"Rebase should be called only once, called {len(rebase_history)} times"

        with then("pipeline was checked minimal times (no retry loop)"):
            # Pipeline is checked once in _wait_for_rebase (to get pipeline id)
            # and once in _wait_for_pipeline (where it fails immediately)
            # Total: 2 checks, not more (no retry polling loop)
            pipelines_history = await pipelines_mock.fetch_history()
            assert len(pipelines_history) == 2, (
                f"Pipeline should be checked exactly twice (rebase + wait), checked {len(pipelines_history)} times"
            )


__all__ = [
    "non_actionable_status_does_not_retry",
    "process_mr_with_non_actionable_pipeline_status",
]
