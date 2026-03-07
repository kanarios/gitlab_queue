"""Integration test scenarios for webhook flow.

Tests WebhookHandler with FakeGitLabClient + FakeQueueManager + FakeNotifier
instead of real Database + GitLabMockTransport.
"""

from __future__ import annotations

from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeQueueManager, create_mr
from scenarios.unit.processor._helpers import create_test_queue_item
from vedro import given, scenario, then, when

from gitlab_queue.webhooks.handlers import WebhookHandler


@scenario()
async def webhook_mr_labeled_flow():
    """Test MR labeled event adds MR to queue."""

    with given("webhook handler with fake collaborators"):
        settings = created_test_settings(webhook_secret="test-secret")
        gitlab_client = FakeGitLabClient(
            mr_responses={
                100: create_mr(
                    iid=100,
                    title="Feature from Webhook",
                    labels=["merge_queue", "feature"],
                    sha="webhook123",
                ),
            },
        )
        queue_manager = FakeQueueManager()
        notifier = FakeNotifier()

        webhook_handler = WebhookHandler(
            queue_manager=queue_manager,
            gitlab_client=gitlab_client,
            settings=settings,
            notifier=notifier,
        )

        webhook_payload = {
            "object_kind": "merge_request",
            "event_type": "merge_request",
            "project": {"id": 123},
            "object_attributes": {
                "iid": 100,
                "title": "Feature from Webhook",
                "state": "opened",
                "source_branch": "feature/webhook",
                "target_branch": "main",
                "last_commit": {"id": "webhook123"},
                "action": "labeled",
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

    with when("webhook receives MR labeled event"):
        await webhook_handler.handle_merge_request_event(webhook_payload)

    with then("MR is added to queue"):
        assert len(queue_manager.add_to_queue_calls) == 1
        assert queue_manager.add_to_queue_calls[0]["mr"].iid == 100
        assert queue_manager.add_to_queue_calls[0]["is_hotfix"] is False


@scenario()
async def webhook_mr_unlabeled_flow():
    """Test MR unlabeled event removes MR from queue."""

    with given("MR already in queue and unlabel webhook payload"):
        settings = created_test_settings(webhook_secret="test-secret")
        gitlab_client = FakeGitLabClient()
        queue_manager = FakeQueueManager()
        notifier = FakeNotifier()

        queue_manager.add_item(create_test_queue_item(mr_iid=101))

        webhook_handler = WebhookHandler(
            queue_manager=queue_manager,
            gitlab_client=gitlab_client,
            settings=settings,
            notifier=notifier,
        )

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
                "action": "unlabeled",
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
        await webhook_handler.handle_merge_request_event(webhook_payload)

    with then("MR is removed from queue"):
        assert len(queue_manager.complete_calls) == 1
        assert queue_manager.complete_calls[0]["mr_iid"] == 101
        assert queue_manager.complete_calls[0]["status"] == "removed"


@scenario()
async def webhook_mr_closed_flow():
    """Test MR closed event removes MR from queue and removes label."""

    with given("MR in queue and close webhook payload"):
        settings = created_test_settings(webhook_secret="test-secret")
        gitlab_client = FakeGitLabClient()
        queue_manager = FakeQueueManager()
        notifier = FakeNotifier()

        queue_manager.add_item(create_test_queue_item(mr_iid=102))

        webhook_handler = WebhookHandler(
            queue_manager=queue_manager,
            gitlab_client=gitlab_client,
            settings=settings,
            notifier=notifier,
        )

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
        await webhook_handler.handle_merge_request_event(webhook_payload)

    with then("MR is removed from queue"):
        assert len(queue_manager.complete_calls) == 1
        assert queue_manager.complete_calls[0]["mr_iid"] == 102
        assert queue_manager.complete_calls[0]["status"] == "removed"
        assert len(notifier.notify_calls) >= 1


@scenario()
async def webhook_hotfix_priority_flow():
    """Test hotfix MR is added with hotfix priority."""

    with given("regular MR in queue and hotfix webhook payload"):
        settings = created_test_settings(webhook_secret="test-secret")
        gitlab_client = FakeGitLabClient(
            mr_responses={
                104: create_mr(
                    iid=104,
                    title="HOTFIX: Critical Bug",
                    labels=["merge_queue", "hotfix"],
                    sha="hotfix123",
                ),
            },
        )
        queue_manager = FakeQueueManager()
        notifier = FakeNotifier()

        queue_manager.add_item(create_test_queue_item(mr_iid=103))

        webhook_handler = WebhookHandler(
            queue_manager=queue_manager,
            gitlab_client=gitlab_client,
            settings=settings,
            notifier=notifier,
        )

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
                "action": "labeled",
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

    with when("webhook receives hotfix MR labeled event"):
        await webhook_handler.handle_merge_request_event(webhook_payload)

    with then("hotfix MR is added to queue with hotfix flag"):
        assert len(queue_manager.add_to_queue_calls) == 1
        assert queue_manager.add_to_queue_calls[0]["mr"].iid == 104
        assert queue_manager.add_to_queue_calls[0]["is_hotfix"] is True


@scenario()
async def webhook_authentication_validation():
    """Test webhook authentication and validation."""

    with given("webhook handler with secret configured"):
        settings = created_test_settings(webhook_secret="correct-secret")
        gitlab_client = FakeGitLabClient()
        queue_manager = FakeQueueManager()
        notifier = FakeNotifier()

        webhook_handler = WebhookHandler(
            queue_manager=queue_manager,
            gitlab_client=gitlab_client,
            settings=settings,
            notifier=notifier,
        )

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

        invalid_payload = {
            "object_kind": "merge_request",
            "event_type": "merge_request",
            "project": {"id": 999},
            "object_attributes": {
                "iid": 106,
                "title": "Wrong Project",
                "state": "opened",
                "source_branch": "feature/wrong",
                "target_branch": "main",
            },
        }

    with when("webhook validates authentication"):
        valid_result = await webhook_handler.validate_webhook(
            valid_payload,
            secret_token="correct-secret",
        )
        invalid_secret_result = await webhook_handler.validate_webhook(
            valid_payload,
            secret_token="wrong-secret",
        )
        invalid_project_result = await webhook_handler.validate_webhook(
            invalid_payload,
            secret_token="correct-secret",
        )

    with then("only valid webhooks are accepted"):
        assert valid_result is True
        assert invalid_secret_result is False
        assert invalid_project_result is False


__all__ = [
    "webhook_authentication_validation",
    "webhook_hotfix_priority_flow",
    "webhook_mr_closed_flow",
    "webhook_mr_labeled_flow",
    "webhook_mr_unlabeled_flow",
]
