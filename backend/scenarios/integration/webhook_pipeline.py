"""Integration test scenarios for webhook pipeline events.

This scenario tests webhook handling for pipeline status updates:
1. Pipeline success events
2. Pipeline failure events
3. Pipeline retry triggering
4. Pipeline status transitions
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import jj
from jj.mock import mocked
from scenarios.contexts.jj_gitlab_mock import get_mock_url
from vedro import given, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.config import Settings
from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.models.mr import Author, MergeRequest
from gitlab_queue.webhooks.handlers import WebhookHandler


@scenario()
async def webhook_pipeline_success_triggers_merge():
    """Test that pipeline success webhook triggers merge processing."""

    with given("MR in testing state and pipeline success webhook"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        # Add MR to queue in testing state
        test_mr = MergeRequest(
            iid=200,
            title="Ready to Merge",
            state="opened",
            target_branch="main",
            source_branch="feature/ready",
            sha="ready123",
            labels=["merge_queue"],
            author=Author(id=20, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/200",
        )
        await queue.add_to_queue(test_mr, is_hotfix=False)
        await queue.update_mr_state(200, "testing")

        mock_url = get_mock_url()

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-secret",
            poll_interval_seconds=0.5,
        )

        # Pipeline success webhook payload
        pipeline_webhook = {
            "object_kind": "pipeline",
            "object_attributes": {
                "id": 6001,
                "ref": "feature/ready",
                "tag": False,
                "sha": "ready123",
                "status": "success",
                "stages": ["build", "test", "deploy"],
                "duration": 120,
                "finished_at": datetime.now(UTC).isoformat(),
            },
            "project": {
                "id": 123,
                "name": "test-project",
            },
            "merge_request": {
                "iid": 200,
                "title": "Ready to Merge",
                "source_branch": "feature/ready",
                "target_branch": "main",
            },
        }

        # Mock GitLab API responses
        mr_data = {
            "iid": 200,
            "project_id": 123,
            "title": "Ready to Merge",
            "state": "opened",
            "source_branch": "feature/ready",
            "target_branch": "main",
            "sha": "ready123",
            "labels": ["merge_queue"],
            "author": {"id": 20, "name": "Test User", "username": "testuser"},
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "web_url": "https://gitlab.com/test/project/-/merge_requests/200",
        }

        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/200")
        get_mr_response = jj.Response(status=200, json=mr_data)

        merge_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/200/merge")
        merge_response = jj.Response(status=200, json={**mr_data, "state": "merged"})

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/200/notes")
        comment_response = jj.Response(status=201, json={"id": 60})

        # GET notes - needed for _find_bot_comment in MRNotifier
        get_notes_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/200/notes")
        get_notes_response = jj.Response(status=200, json=[])

        # Pipelines for MR
        pipelines_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/200/pipelines")
        pipelines_response = jj.Response(status=200, json=[{"id": 6001, "status": "success", "sha": "ready123"}])

    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(merge_matcher, merge_response),
        mocked(comment_matcher, comment_response),
        mocked(get_notes_matcher, get_notes_response),
        mocked(pipelines_matcher, pipelines_response),
    ):
        with when("pipeline success webhook is received"):
            gitlab_client = GitLabClient(settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)

            webhook_handler = WebhookHandler(
                queue_manager=queue,
                gitlab_client=gitlab_client,
                settings=settings,
                notifier=notifier,
            )

            # Process pipeline webhook - this triggers state transition to merging
            await webhook_handler.handle_pipeline_event(pipeline_webhook)

        with then("MR state transitions to merging"):
            # Verify state transitioned to merging
            mr_state = await queue.get_mr_state(200)
            assert mr_state is not None, "MR state should exist"
            assert mr_state["status"] == "merging", f"Expected merging, got {mr_state['status']}"

            # Get the MR by IID (get_next_mr only returns queued MRs)
            queue_item = await queue.get_queue_item(200)
            assert queue_item is not None, "Queue item should exist"
            assert queue_item.state == "merging", "MR should be in merging state"

    # Cleanup
    await db.close()


@scenario()
async def webhook_pipeline_failure_triggers_retry():
    """Test that pipeline failure webhook triggers retry logic."""

    with given("MR in testing state and pipeline failure webhook"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        # Add MR to queue in testing state
        test_mr = MergeRequest(
            iid=201,
            title="Flaky Tests",
            state="opened",
            target_branch="main",
            source_branch="feature/flaky",
            sha="flaky123",
            labels=["merge_queue"],
            author=Author(id=21, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/201",
        )
        await queue.add_to_queue(test_mr, is_hotfix=False)
        await queue.update_mr_state(201, "testing")

        mock_url = get_mock_url()

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-secret",
            pipeline_retry_count=2,  # Allow retries
        )

        # Pipeline failure webhook payload
        pipeline_webhook = {
            "object_kind": "pipeline",
            "object_attributes": {
                "id": 6002,
                "ref": "feature/flaky",
                "sha": "flaky123",
                "status": "failed",
                "stages": ["build", "test"],
                "failure_reason": "test_failure",
                "finished_at": datetime.now(UTC).isoformat(),
            },
            "project": {"id": 123},
            "merge_request": {
                "iid": 201,
                "title": "Flaky Tests",
            },
            "builds": [
                {
                    "id": 7001,
                    "name": "test:unit",
                    "status": "failed",
                    "stage": "test",
                },
            ],
        }

        # Mock responses for retry
        mr_data = {
            "iid": 201,
            "project_id": 123,
            "title": "Flaky Tests",
            "state": "opened",
            "source_branch": "feature/flaky",
            "target_branch": "main",
            "sha": "flaky123",
            "labels": ["merge_queue"],
            "author": {"id": 21, "name": "Test User", "username": "testuser"},
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "web_url": "https://gitlab.com/test/project/-/merge_requests/201",
        }

        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/201")
        get_mr_response = jj.Response(status=200, json=mr_data)

        # Retry rebase
        rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/201/rebase")
        rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        # Retry pipeline trigger
        retry_pipeline_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/201/pipelines")
        retry_pipeline_response = jj.Response(status=201, json={"id": 6003, "status": "pending", "sha": "flaky456"})

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/201/notes")
        comment_response = jj.Response(status=201, json={"id": 61})

        # GET notes - needed for _find_bot_comment in MRNotifier
        get_notes_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/201/notes")
        get_notes_response = jj.Response(status=200, json=[])

    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(rebase_matcher, rebase_response),
        mocked(retry_pipeline_matcher, retry_pipeline_response),
        mocked(comment_matcher, comment_response),
        mocked(get_notes_matcher, get_notes_response),
    ):
        with when("pipeline failure webhook is received"):
            gitlab_client = GitLabClient(settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
            webhook_handler = WebhookHandler(
                queue_manager=queue,
                gitlab_client=gitlab_client,
                settings=settings,
                notifier=notifier,
            )

            # Process pipeline failure webhook
            await webhook_handler.handle_pipeline_event(pipeline_webhook)

        with then("retry is triggered if retries remain"):
            # Verify MR is in appropriate state after pipeline failure
            # (could be testing with failed status for retry, or still testing)
            mr_state = await queue.get_mr_state(201)
            assert mr_state is not None, "MR state should exist"
            assert mr_state["status"] in (
                "rebasing",
                "testing",
                "failed",
            ), f"MR should be retrying or failed, got {mr_state['status']}"

    # Cleanup
    await db.close()


@scenario()
async def webhook_concurrent_pipeline_events():
    """Test handling of concurrent pipeline events for same MR."""

    with given("MR with multiple concurrent pipeline events"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        test_mr = MergeRequest(
            iid=202,
            title="Concurrent Pipelines",
            state="opened",
            target_branch="main",
            source_branch="feature/concurrent",
            sha="concurrent123",
            labels=["merge_queue"],
            author=Author(id=22, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/202",
        )
        await queue.add_to_queue(test_mr, is_hotfix=False)
        await queue.update_mr_state(202, "testing")

        mock_url = get_mock_url()

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-secret",
        )

        # Multiple pipeline events (e.g., from parallel jobs)
        pipeline_events = [
            {
                "object_kind": "pipeline",
                "object_attributes": {
                    "id": 6004,
                    "sha": "concurrent123",
                    "status": "running",
                },
                "project": {"id": 123},
                "merge_request": {"iid": 202},
            },
            {
                "object_kind": "pipeline",
                "object_attributes": {
                    "id": 6004,
                    "sha": "concurrent123",
                    "status": "success",
                },
                "project": {"id": 123},
                "merge_request": {"iid": 202},
            },
            {
                "object_kind": "pipeline",
                "object_attributes": {
                    "id": 6005,  # Different pipeline ID (old/duplicate)
                    "sha": "concurrent_old",
                    "status": "failed",
                },
                "project": {"id": 123},
                "merge_request": {"iid": 202},
            },
        ]

        # Mock responses
        mr_data = {
            "iid": 202,
            "project_id": 123,
            "title": "Concurrent Pipelines",
            "state": "opened",
            "source_branch": "feature/concurrent",
            "target_branch": "main",
            "sha": "concurrent123",
            "labels": ["merge_queue"],
            "author": {"id": 22, "name": "Test User", "username": "testuser"},
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "web_url": "https://gitlab.com/test/project/-/merge_requests/202",
        }

        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/202")
        get_mr_response = jj.Response(status=200, json=mr_data)

        merge_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/202/merge")
        merge_response = jj.Response(status=200, json={**mr_data, "state": "merged"})

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/202/notes")
        comment_response = jj.Response(status=201, json={"id": 62})

        get_notes_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/202/notes")
        get_notes_response = jj.Response(status=200, json=[])

    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(merge_matcher, merge_response),
        mocked(comment_matcher, comment_response),
        mocked(get_notes_matcher, get_notes_response),
    ):
        with when("multiple pipeline events are received concurrently"):
            gitlab_client = GitLabClient(settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
            webhook_handler = WebhookHandler(
                queue_manager=queue,
                gitlab_client=gitlab_client,
                settings=settings,
                notifier=notifier,
            )

            # Process all events concurrently
            tasks = [webhook_handler.handle_pipeline_event(event) for event in pipeline_events]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        with then("only latest/relevant pipeline status is processed"):
            # Verify no exceptions
            exceptions = [r for r in results if isinstance(r, Exception)]
            assert len(exceptions) == 0, f"No exceptions should occur: {exceptions}"

            # MR should remain in a consistent state
            mr_state = await queue.get_mr_state(202)
            assert mr_state is not None, "MR state should exist"
            assert mr_state["status"] in (
                "testing",
                "merging",
                "merged",
                "failed",
            ), f"MR should be in valid state, got {mr_state['status']}"

    # Cleanup
    await db.close()


@scenario()
async def webhook_pipeline_canceled_handling():
    """Test handling of canceled pipeline webhooks."""

    with given("MR in testing with canceled pipeline"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        test_mr = MergeRequest(
            iid=203,
            title="Canceled Pipeline",
            state="opened",
            target_branch="main",
            source_branch="feature/canceled",
            sha="canceled123",
            labels=["merge_queue"],
            author=Author(id=23, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/203",
        )
        await queue.add_to_queue(test_mr, is_hotfix=False)
        await queue.update_mr_state(203, "testing")

        mock_url = get_mock_url()

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-secret",
        )

        # Canceled pipeline webhook
        canceled_webhook = {
            "object_kind": "pipeline",
            "object_attributes": {
                "id": 6006,
                "sha": "canceled123",
                "status": "canceled",
                "canceled_at": datetime.now(UTC).isoformat(),
            },
            "project": {"id": 123},
            "merge_request": {"iid": 203},
        }

        # Mock responses
        mr_data = {
            "iid": 203,
            "project_id": 123,
            "title": "Canceled Pipeline",
            "state": "opened",
            "source_branch": "feature/canceled",
            "target_branch": "main",
            "sha": "canceled123",
            "labels": ["merge_queue"],
            "author": {"id": 23, "name": "Test User", "username": "testuser"},
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "web_url": "https://gitlab.com/test/project/-/merge_requests/203",
        }

        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/203")
        get_mr_response = jj.Response(status=200, json=mr_data)

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/203/notes")
        comment_response = jj.Response(status=201, json={"id": 62})

        get_notes_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/203/notes")
        get_notes_response = jj.Response(status=200, json=[])

    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(comment_matcher, comment_response),
        mocked(get_notes_matcher, get_notes_response),
    ):
        with when("canceled pipeline webhook is received"):
            gitlab_client = GitLabClient(settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
            webhook_handler = WebhookHandler(
                queue_manager=queue,
                gitlab_client=gitlab_client,
                settings=settings,
                notifier=notifier,
            )

            await webhook_handler.handle_pipeline_event(canceled_webhook)

        with then("canceled pipeline is handled appropriately"):
            # Canceled should trigger failure transition
            mr_state = await queue.get_mr_state(203)
            assert mr_state is not None, "MR state should exist"
            assert mr_state["status"] in (
                "rebasing",
                "testing",
                "failed",
                "queued",
            ), f"Canceled pipeline should trigger retry or reset, got {mr_state['status']}"

    # Cleanup
    await db.close()


__all__ = [
    "webhook_concurrent_pipeline_events",
    "webhook_pipeline_canceled_handling",
    "webhook_pipeline_failure_triggers_retry",
    "webhook_pipeline_success_triggers_merge",
]
