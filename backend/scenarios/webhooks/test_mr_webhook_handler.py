"""Unit tests for MRWebhookHandler."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.models.events import (
    LabelChanges,
    MergeRequestAttributes,
    MergeRequestEvent,
)
from gitlab_queue.models.mr import Author, MergeRequest
from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler


def create_mock_settings(queue_label: str = "merge_queue", hotfix_label: str = "hotfix"):
    """Create mock settings."""
    settings = MagicMock()
    settings.queue_label = queue_label
    settings.hotfix_label = hotfix_label
    return settings


def create_mock_gitlab_client():
    """Create mock GitLab client."""
    client = MagicMock()
    client.get_mr = AsyncMock(
        return_value=MergeRequest(
            iid=123,
            title="Test MR",
            state="opened",
            labels=["merge_queue"],
            sha="abc123",
            source_branch="feature",
            target_branch="master",
            merge_status="can_be_merged",
            author=Author(id=1, name="Test", username="test"),
        )
    )
    return client


def create_mock_queue_manager():
    """Create mock queue manager."""
    qm = MagicMock()
    qm.add_to_queue = AsyncMock()
    qm.remove_from_queue = AsyncMock(return_value=True)
    qm.get_queue_item = AsyncMock(return_value=None)
    qm.update_mr_state = AsyncMock(return_value=True)
    return qm


def create_mr_event(
    iid: int = 123,
    action: str = "labeled",
    state: str = "opened",
    previous_labels: list[str] | None = None,
    current_labels: list[str] | None = None,
    event_labels: list[str] | None = None,
) -> MergeRequestEvent:
    """Create a MergeRequestEvent for testing."""
    label_changes = None
    if previous_labels is not None or current_labels is not None:
        label_changes = LabelChanges(
            previous=previous_labels or [],
            current=current_labels or [],
        )

    return MergeRequestEvent(
        object_kind="merge_request",
        event_type="merge_request",
        project_id=42,
        object_attributes=MergeRequestAttributes(
            iid=iid,
            title="Test MR",
            state=state,
            action=action,
            source_branch="feature",
            target_branch="master",
            merge_status="can_be_merged",
        ),
        user_id=1,
        user_name="Test User",
        user_username="testuser",
        labels=event_labels or [],
        label_changes=label_changes,
    )


class Scenario(vedro.Scenario):
    subject = "detect queue label added"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=create_mock_queue_manager(),
        )
        self.event = create_mr_event(
            action="labeled",
            previous_labels=[],
            current_labels=["merge_queue"],
        )

    def when_checking_if_queue_label_added(self):
        self.result = self.handler._was_queue_label_added(self.event)

    def then_it_should_return_true(self):
        assert self.result is True


class Scenario__queue_label_not_added(vedro.Scenario):
    subject = "detect queue label not added"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=create_mock_queue_manager(),
        )
        self.event = create_mr_event(
            action="labeled",
            previous_labels=[],
            current_labels=["other_label"],
        )

    def when_checking_if_queue_label_added(self):
        self.result = self.handler._was_queue_label_added(self.event)

    def then_it_should_return_false(self):
        assert self.result is False


class Scenario__detect_queue_label_removed(vedro.Scenario):
    subject = "detect queue label removed"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=create_mock_queue_manager(),
        )
        self.event = create_mr_event(
            action="unlabeled",
            previous_labels=["merge_queue"],
            current_labels=[],
        )

    def when_checking_if_queue_label_removed(self):
        self.result = self.handler._was_queue_label_removed(self.event)

    def then_it_should_return_true(self):
        assert self.result is True


class Scenario__queue_label_not_removed(vedro.Scenario):
    subject = "detect queue label not removed"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=create_mock_queue_manager(),
        )
        self.event = create_mr_event(
            action="unlabeled",
            previous_labels=["other_label"],
            current_labels=[],
        )

    def when_checking_if_queue_label_removed(self):
        self.result = self.handler._was_queue_label_removed(self.event)

    def then_it_should_return_false(self):
        assert self.result is False


class Scenario__no_label_changes(vedro.Scenario):
    subject = "handle event without label changes"

    def given_handler_and_event_without_changes(self):
        self.settings = create_mock_settings()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=create_mock_queue_manager(),
        )
        self.event = create_mr_event(action="update")  # No label_changes

    def when_checking_label_operations(self):
        self.added = self.handler._was_queue_label_added(self.event)
        self.removed = self.handler._was_queue_label_removed(self.event)

    def then_both_should_return_false(self):
        assert self.added is False
        assert self.removed is False


class Scenario__handle_labeled_action(vedro.Scenario):
    subject = "handle labeled action adds MR to queue"

    def given_handler(self):
        self.settings = create_mock_settings()
        self.gitlab_client = create_mock_gitlab_client()
        self.queue_manager = create_mock_queue_manager()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        self.event = create_mr_event(
            action="labeled",
            previous_labels=[],
            current_labels=["merge_queue"],
            event_labels=["merge_queue"],
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_fetched_and_added(self):
        self.gitlab_client.get_mr.assert_called_once_with(123)
        self.queue_manager.add_to_queue.assert_called_once()


class Scenario__handle_labeled_with_hotfix(vedro.Scenario):
    subject = "handle labeled action with hotfix label"

    def given_handler(self):
        self.settings = create_mock_settings()
        self.gitlab_client = create_mock_gitlab_client()
        self.queue_manager = create_mock_queue_manager()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        self.event = create_mr_event(
            action="labeled",
            previous_labels=[],
            current_labels=["merge_queue", "hotfix"],
            event_labels=["merge_queue", "hotfix"],
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_added_as_hotfix(self):
        call_args = self.queue_manager.add_to_queue.call_args
        assert call_args[1]["is_hotfix"] is True


class Scenario__handle_unlabeled_action(vedro.Scenario):
    subject = "handle unlabeled action removes MR from queue"

    def given_handler(self):
        self.settings = create_mock_settings()
        self.gitlab_client = create_mock_gitlab_client()
        self.queue_manager = create_mock_queue_manager()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        self.event = create_mr_event(
            action="unlabeled",
            previous_labels=["merge_queue"],
            current_labels=[],
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_removed_from_queue(self):
        self.queue_manager.remove_from_queue.assert_called_once_with(123)


class Scenario__handle_merge_action(vedro.Scenario):
    subject = "handle merge action cleans up queue"

    def given_handler(self):
        self.settings = create_mock_settings()
        self.gitlab_client = create_mock_gitlab_client()
        self.queue_manager = create_mock_queue_manager()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        self.event = create_mr_event(action="merge", state="merged")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_removed_from_queue(self):
        self.queue_manager.remove_from_queue.assert_called_once_with(123)


class Scenario__handle_close_action(vedro.Scenario):
    subject = "handle close action removes MR from queue"

    def given_handler(self):
        self.settings = create_mock_settings()
        self.gitlab_client = create_mock_gitlab_client()
        self.queue_manager = create_mock_queue_manager()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        self.event = create_mr_event(action="close", state="closed")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_removed_from_queue(self):
        self.queue_manager.remove_from_queue.assert_called_once_with(123)


class Scenario__handle_update_resets_processing_mr(vedro.Scenario):
    subject = "handle update resets MR in processing state"

    def given_handler_with_processing_mr(self):
        self.settings = create_mock_settings()
        self.gitlab_client = create_mock_gitlab_client()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=QueueItem(
                mr_iid=123,
                title="Test",
                author_name="Test",
                author_username="test",
                target_branch="master",
                state="rebasing",  # Processing state
                queued_at=datetime.now(UTC),
            )
        )
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        self.event = create_mr_event(action="update")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_reset_to_queued(self):
        self.queue_manager.update_mr_state.assert_called_once_with(123, "queued")


class Scenario__handle_update_ignores_queued_mr(vedro.Scenario):
    subject = "handle update ignores MR in queued state"

    def given_handler_with_queued_mr(self):
        self.settings = create_mock_settings()
        self.gitlab_client = create_mock_gitlab_client()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=QueueItem(
                mr_iid=123,
                title="Test",
                author_name="Test",
                author_username="test",
                target_branch="master",
                state="queued",
                queued_at=datetime.now(UTC),
            )
        )
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        self.event = create_mr_event(action="update")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_state_should_not_be_updated(self):
        self.queue_manager.update_mr_state.assert_not_called()


class Scenario__handle_unknown_action(vedro.Scenario):
    subject = "handle unknown action is ignored"

    def given_handler(self):
        self.settings = create_mock_settings()
        self.gitlab_client = create_mock_gitlab_client()
        self.queue_manager = create_mock_queue_manager()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        self.event = create_mr_event(action="approved")  # Unknown action

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_no_queue_operations_should_happen(self):
        self.queue_manager.add_to_queue.assert_not_called()
        self.queue_manager.remove_from_queue.assert_not_called()
        self.queue_manager.update_mr_state.assert_not_called()
