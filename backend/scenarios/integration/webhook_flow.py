"""Integration test scenarios for webhook flow.

This scenario tests the complete webhook flow:
1. Receiving webhook events
2. Processing queue changes via webhooks
3. Webhook validation and authentication
4. Error handling for webhook failures
"""

from __future__ import annotations

import jj
from jj.mock import mocked
from scenarios.contexts.jj_gitlab_mock import get_mock_url
from vedro import given, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.config import Settings
from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.processor import MergeProcessor
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.models.mr import Author, MergeRequest
from gitlab_queue.webhooks.handlers import WebhookHandler


@scenario()
async def webhook_mr_labeled_flow():
    """Test complete flow when MR is labeled with merge_queue label."""

    with given("webhook handler and processor configured"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

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

        # Webhook payload for MR labeled event - action must be "labeled"
        webhook_payload = {
            "object_kind": "merge_request",
            "event_type": "merge_request",
            "project": {
                "id": 123,
                "name": "test-project",
            },
            "object_attributes": {
                "iid": 100,
                "title": "Feature from Webhook",
                "state": "opened",
                "source_branch": "feature/webhook",
                "target_branch": "main",
                "last_commit": {"id": "webhook123"},
                "action": "labeled",  # Must be "labeled" for add to queue
            },
            "labels": [
                {"title": "merge_queue"},
                {"title": "feature"},
            ],
            "changes": {
                "labels": {
                    "previous": [],
                    "current": [{"title": "merge_queue"}, {"title": "feature"}],
                },
            },
        }

        # Mock GitLab API responses
        mr_data = {
            "iid": 100,
            "project_id": 123,
            "title": "Feature from Webhook",
            "state": "opened",
            "source_branch": "feature/webhook",
            "target_branch": "main",
            "sha": "webhook123",
            "labels": ["merge_queue", "feature"],
            "author": {"id": 10, "name": "Webhook User", "username": "webhook_user"},
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "web_url": "https://gitlab.com/test/project/-/merge_requests/100",
        }

        pipeline_data = {
            "id": 5001,
            "status": "success",
            "sha": "webhook123",
        }

        # Setup matchers
        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/100")
        get_mr_response = jj.Response(status=200, json=mr_data)

        rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/100/rebase")
        rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        pipelines_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/100/pipelines")
        pipelines_response = jj.Response(status=200, json=[pipeline_data])

        merge_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/100/merge")
        merge_response = jj.Response(status=200, json={**mr_data, "state": "merged"})

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/100/notes")
        comment_response = jj.Response(status=201, json={"id": 50})

        # GET notes - needed for _find_bot_comment in MRNotifier
        get_notes_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/100/notes")
        get_notes_response = jj.Response(status=200, json=[])

    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(rebase_matcher, rebase_response),
        mocked(pipelines_matcher, pipelines_response),
        mocked(merge_matcher, merge_response) as merge_mock,
        mocked(comment_matcher, comment_response),
        mocked(get_notes_matcher, get_notes_response),
    ):
        with when("webhook receives MR labeled event and processor runs"):
            gitlab_client = GitLabClient(settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
            processor = MergeProcessor(
                gitlab_client=gitlab_client,
                queue_manager=queue,
                notifier=notifier,
                settings=settings,
            )

            webhook_handler = WebhookHandler(
                queue_manager=queue,
                gitlab_client=gitlab_client,
                settings=settings,
            )

            # Process webhook
            await webhook_handler.handle_merge_request_event(webhook_payload)

            # Verify MR was added to queue
            queue_state = await queue.get_active_queue()
            assert len(queue_state) == 1, "MR should be in queue"
            assert queue_state[0].mr_iid == 100

            # Run processor to merge the MR
            queue_item = await queue.get_next_mr()
            result = await processor._process_mr(queue_item)

        with then("MR is added to queue and successfully merged"):
            assert result.value == "success"

            # Verify merge was called
            merge_history = await merge_mock.fetch_history()
            assert len(merge_history) == 1, "Merge should have been called"

            # Verify final state
            mr_state = await queue.get_mr_state(100)
            assert mr_state["status"] == "merged"

    # Cleanup
    await db.close()


@scenario()
async def webhook_mr_unlabeled_flow():
    """Test flow when MR is unlabeled (removed from queue)."""

    with given("MR in queue and webhook for unlabel event"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        # Add MR to queue first
        test_mr = MergeRequest(
            iid=101,
            title="To Be Removed",
            state="opened",
            target_branch="main",
            source_branch="feature/remove",
            sha="remove123",
            labels=["merge_queue"],
            author=Author(id=11, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/101",
        )
        await queue.add_to_queue(test_mr, is_hotfix=False)

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

        # Webhook payload for MR unlabeled event - action must be "unlabeled"
        webhook_payload = {
            "object_kind": "merge_request",
            "event_type": "merge_request",
            "project": {"id": 123},
            "object_attributes": {
                "iid": 101,
                "title": "To Be Removed",
                "state": "opened",
                "source_branch": "feature/remove",
                "target_branch": "main",
                "action": "unlabeled",  # Must be "unlabeled" for removal
            },
            "labels": [],
            "changes": {
                "labels": {
                    "previous": [{"title": "merge_queue"}],
                    "current": [],
                },
            },
        }

    with when("webhook receives MR unlabeled event"):
        gitlab_client = GitLabClient(settings)
        webhook_handler = WebhookHandler(
            queue_manager=queue,
            gitlab_client=gitlab_client,
            settings=settings,
        )

        # Process webhook
        await webhook_handler.handle_merge_request_event(webhook_payload)

    with then("MR is removed from queue"):
        # Verify MR was removed from queue
        queue_state = await queue.get_active_queue()
        assert len(queue_state) == 0, "Queue should be empty"

        # Verify MR state
        mr_state = await queue.get_mr_state(101)
        assert mr_state is None or mr_state["status"] == "removed"

    # Cleanup
    await db.close()


@scenario()
async def webhook_mr_closed_flow():
    """Test flow when MR is closed via webhook."""

    with given("MR in queue and webhook for close event"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        # Add MR to queue
        test_mr = MergeRequest(
            iid=102,
            title="To Be Closed",
            state="opened",
            target_branch="main",
            source_branch="feature/close",
            sha="close123",
            labels=["merge_queue"],
            author=Author(id=12, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/102",
        )
        await queue.add_to_queue(test_mr, is_hotfix=False)

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

        # Webhook payload for MR closed event
        webhook_payload = {
            "object_kind": "merge_request",
            "event_type": "merge_request",
            "project": {"id": 123},
            "object_attributes": {
                "iid": 102,
                "title": "To Be Closed",
                "state": "closed",
                "source_branch": "feature/close",
                "target_branch": "main",
                "action": "close",
            },
            "labels": [{"title": "merge_queue"}],
        }

    with when("webhook receives MR closed event"):
        gitlab_client = GitLabClient(settings)
        webhook_handler = WebhookHandler(
            queue_manager=queue,
            gitlab_client=gitlab_client,
            settings=settings,
        )

        # Process webhook
        await webhook_handler.handle_merge_request_event(webhook_payload)

    with then("MR is removed from queue"):
        # Verify MR was removed from queue
        queue_state = await queue.get_active_queue()
        assert len(queue_state) == 0, "Queue should be empty after MR closed"

        # Verify MR state
        mr_state = await queue.get_mr_state(102)
        assert mr_state is None or mr_state["status"] == "removed"

    # Cleanup
    await db.close()


@scenario()
async def webhook_hotfix_priority_flow():
    """Test webhook flow with hotfix priority."""

    with given("regular MR in queue and hotfix webhook received"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        # Add regular MR to queue
        regular_mr = MergeRequest(
            iid=103,
            title="Regular Feature",
            state="opened",
            target_branch="main",
            source_branch="feature/regular",
            sha="regular123",
            labels=["merge_queue"],
            author=Author(id=13, name="Regular User", username="regular"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/103",
        )
        await queue.add_to_queue(regular_mr, is_hotfix=False)

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

        # Webhook payload for hotfix MR - action must be "labeled"
        webhook_payload = {
            "object_kind": "merge_request",
            "event_type": "merge_request",
            "project": {"id": 123},
            "object_attributes": {
                "iid": 104,
                "title": "HOTFIX: Critical Bug",
                "state": "opened",
                "source_branch": "hotfix/critical",
                "target_branch": "main",
                "last_commit": {"id": "hotfix123"},
                "action": "labeled",  # Must be "labeled" for add to queue
            },
            "labels": [
                {"title": "merge_queue"},
                {"title": "hotfix"},
            ],
            "changes": {
                "labels": {
                    "previous": [],
                    "current": [{"title": "merge_queue"}, {"title": "hotfix"}],
                },
            },
        }

        # Mock GitLab API response for hotfix MR
        hotfix_mr_data = {
            "iid": 104,
            "project_id": 123,
            "title": "HOTFIX: Critical Bug",
            "state": "opened",
            "source_branch": "hotfix/critical",
            "target_branch": "main",
            "sha": "hotfix123",
            "labels": ["merge_queue", "hotfix"],
            "author": {"id": 14, "name": "Hotfix User", "username": "hotfix_user"},
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "web_url": "https://gitlab.com/test/project/-/merge_requests/104",
        }

        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/104")
        get_mr_response = jj.Response(status=200, json=hotfix_mr_data)

    async with mocked(get_mr_matcher, get_mr_response):
        with when("webhook receives hotfix MR labeled event"):
            gitlab_client = GitLabClient(settings)
            webhook_handler = WebhookHandler(
                queue_manager=queue,
                gitlab_client=gitlab_client,
                settings=settings,
            )

            # Process webhook
            await webhook_handler.handle_merge_request_event(webhook_payload)

        with then("hotfix MR gets priority in queue"):
            # Verify queue order - hotfix should be first
            queue_state = await queue.get_active_queue()
            assert len(queue_state) == 2, "Both MRs should be in queue"

            # Get next MR should return hotfix (104) not regular (103)
            next_mr = await queue.get_next_mr()
            assert next_mr is not None
            assert next_mr.mr_iid == 104, "Hotfix should have priority"

            # Verify regular MR is still in queue
            await queue.update_mr_state(104, "merged")  # Mark hotfix as done
            next_mr = await queue.get_next_mr()
            assert next_mr is not None
            assert next_mr.mr_iid == 103, "Regular MR should still be in queue"

    # Cleanup
    await db.close()


@scenario()
async def webhook_authentication_validation():
    """Test webhook authentication and validation."""

    with given("webhook handler with secret configured"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        mock_url = get_mock_url()

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="correct-secret",
        )

        # Valid webhook payload
        valid_payload = {
            "object_kind": "merge_request",
            "event_type": "merge_request",
            "project": {"id": 123},
            "object_attributes": {
                "iid": 105,
                "title": "Test Auth",
                "state": "opened",
                "source_branch": "feature/auth",
                "target_branch": "main",
                "action": "update",
            },
        }

        # Invalid payload (wrong project)
        invalid_payload = {
            "object_kind": "merge_request",
            "event_type": "merge_request",
            "project": {"id": 999},  # Wrong project ID
            "object_attributes": {
                "iid": 106,
                "title": "Wrong Project",
                "state": "opened",
                "source_branch": "feature/wrong",
                "target_branch": "main",
            },
        }

    with when("webhook validates authentication"):
        gitlab_client = GitLabClient(settings)
        webhook_handler = WebhookHandler(
            queue_manager=queue,
            gitlab_client=gitlab_client,
            settings=settings,
        )

        # Test with correct secret (would be in headers in real implementation)
        valid_result = await webhook_handler.validate_webhook(valid_payload, secret_token="correct-secret")

        # Test with wrong secret
        invalid_secret_result = await webhook_handler.validate_webhook(valid_payload, secret_token="wrong-secret")

        # Test with wrong project
        invalid_project_result = await webhook_handler.validate_webhook(invalid_payload, secret_token="correct-secret")

    with then("only valid webhooks are accepted"):
        assert valid_result is True, "Valid webhook should be accepted"
        assert invalid_secret_result is False, "Wrong secret should be rejected"
        assert invalid_project_result is False, "Wrong project should be rejected"

    # Cleanup
    await db.close()


__all__ = [
    "webhook_authentication_validation",
    "webhook_hotfix_priority_flow",
    "webhook_mr_closed_flow",
    "webhook_mr_labeled_flow",
    "webhook_mr_unlabeled_flow",
]
