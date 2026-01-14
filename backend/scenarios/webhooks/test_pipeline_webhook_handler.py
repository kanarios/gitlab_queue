"""Unit tests for PipelineWebhookHandler."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.models.events import PipelineAttributes, PipelineEvent
from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import PipelineWebhookHandler


def create_mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.queue_label = "merge_queue"
    settings.hotfix_label = "hotfix"
    settings.pipeline_retry_count = 2
    settings.target_branch = "master"
    return settings


def create_mock_gitlab_client():
    """Create mock GitLab client."""
    client = MagicMock()
    return client


def create_mock_queue_manager():
    """Create mock queue manager."""
    qm = MagicMock()
    qm.get_queue_item = AsyncMock(return_value=None)
    qm.update_mr_state = AsyncMock(return_value=True)
    return qm


def create_mock_notifier():
    """Create mock notifier."""
    notifier = MagicMock()
    notifier.notify = AsyncMock()
    return notifier


def create_pipeline_event(
    pipeline_id: int = 456,
    status: str = "success",
    mr_iid: int | None = 123,
) -> PipelineEvent:
    """Create a PipelineEvent for testing."""
    return PipelineEvent(
        object_kind="pipeline",
        project_id=42,
        object_attributes=PipelineAttributes(
            id=pipeline_id,
            status=status,
            sha="abc123",
            ref="feature-branch",
        ),
        merge_request_iid=mr_iid,
    )


def create_queue_item_in_state(state: str, retry_count: int = 0) -> QueueItem:
    """Create a QueueItem in the specified state."""
    return QueueItem(
        mr_iid=123,
        title="Test MR",
        author_name="Test",
        author_username="test",
        target_branch="master",
        state=state,
        queued_at=datetime.now(UTC),
        retry_count=retry_count,
    )


class Scenario(vedro.Scenario):
    subject = "ignore pipeline without MR association"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.queue_manager = create_mock_queue_manager()
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
        )
        self.event = create_pipeline_event(mr_iid=None)

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_no_queue_operations_should_happen(self):
        self.queue_manager.get_queue_item.assert_not_called()


class Scenario__ignore_pipeline_for_mr_not_in_queue(vedro.Scenario):
    subject = "ignore pipeline for MR not in queue"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(return_value=None)
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
        )
        self.event = create_pipeline_event(status="success")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_queue_item_should_be_checked(self):
        self.queue_manager.get_queue_item.assert_called_once_with(123)

    def and_no_state_update_should_happen(self):
        self.queue_manager.update_mr_state.assert_not_called()


class Scenario__ignore_pipeline_for_mr_not_in_testing_state(vedro.Scenario):
    subject = "ignore pipeline success for MR not in testing state"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=create_queue_item_in_state("queued")
        )
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
        )
        self.event = create_pipeline_event(status="success")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_no_state_update_should_happen(self):
        self.queue_manager.update_mr_state.assert_not_called()


class Scenario__handle_pipeline_success(vedro.Scenario):
    subject = "handle pipeline success triggers state machine"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=create_queue_item_in_state("testing")
        )
        self.notifier = create_mock_notifier()
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=self.queue_manager,
            notifier=self.notifier,
        )
        self.event = create_pipeline_event(status="success")

    async def when_event_is_handled(self):
        with patch("gitlab_queue.webhooks.handlers.create_state_machine_for_mr") as mock_sm:
            mock_state_machine = MagicMock()
            mock_state_machine.trigger_pipeline_success = AsyncMock()
            mock_sm.return_value = mock_state_machine
            await self.handler.handle(self.event)
            self.mock_sm = mock_sm
            self.mock_state_machine = mock_state_machine

    def then_state_machine_should_be_created(self):
        self.mock_sm.assert_called_once()

    def and_pipeline_success_should_be_triggered(self):
        self.mock_state_machine.trigger_pipeline_success.assert_called_once()


class Scenario__handle_pipeline_failed_with_retries_left(vedro.Scenario):
    subject = "handle pipeline failed when retries available"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.settings.pipeline_retry_count = 3
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=create_queue_item_in_state("testing", retry_count=1)
        )
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
        )
        self.event = create_pipeline_event(status="failed")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_marked_for_retry(self):
        self.queue_manager.update_mr_state.assert_called_once_with(
            123,
            "testing",
            pipeline_status="failed",
        )


class Scenario__handle_pipeline_failed_no_retries_left(vedro.Scenario):
    subject = "handle pipeline failed when no retries left"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.settings.pipeline_retry_count = 2
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=create_queue_item_in_state("testing", retry_count=3)
        )
        self.notifier = create_mock_notifier()
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=self.queue_manager,
            notifier=self.notifier,
        )
        self.event = create_pipeline_event(status="failed")

    async def when_event_is_handled(self):
        with patch("gitlab_queue.webhooks.handlers.create_state_machine_for_mr") as mock_sm:
            mock_state_machine = MagicMock()
            mock_state_machine.trigger_pipeline_failed = AsyncMock()
            mock_sm.return_value = mock_state_machine
            await self.handler.handle(self.event)
            self.mock_state_machine = mock_state_machine

    def then_pipeline_failed_should_be_triggered(self):
        self.mock_state_machine.trigger_pipeline_failed.assert_called_once()


class Scenario__handle_pipeline_canceled(vedro.Scenario):
    subject = "handle pipeline canceled fails MR without retry"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=create_queue_item_in_state("testing", retry_count=0)
        )
        self.notifier = create_mock_notifier()
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=self.queue_manager,
            notifier=self.notifier,
        )
        self.event = create_pipeline_event(status="canceled")

    async def when_event_is_handled(self):
        with patch("gitlab_queue.webhooks.handlers.create_state_machine_for_mr") as mock_sm:
            mock_state_machine = MagicMock()
            mock_state_machine.trigger_pipeline_failed = AsyncMock()
            mock_sm.return_value = mock_state_machine
            await self.handler.handle(self.event)
            self.mock_state_machine = mock_state_machine

    def then_pipeline_failed_should_be_triggered(self):
        self.mock_state_machine.trigger_pipeline_failed.assert_called_once()


class Scenario__ignore_running_pipeline(vedro.Scenario):
    subject = "ignore running pipeline status"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=create_queue_item_in_state("testing")
        )
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
        )
        self.event = create_pipeline_event(status="running")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_no_state_update_should_happen(self):
        self.queue_manager.update_mr_state.assert_not_called()


class Scenario__ignore_pending_pipeline(vedro.Scenario):
    subject = "ignore pending pipeline status"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.queue_manager = create_mock_queue_manager()
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=create_mock_gitlab_client(),
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
        )
        self.event = create_pipeline_event(status="pending")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_queue_item_should_not_be_checked(self):
        # pending status is not in handled statuses
        self.queue_manager.get_queue_item.assert_not_called()
