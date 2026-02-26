"""Test: pipeline event with SHA mismatch is skipped.

When a pipeline webhook event arrives for an MR in testing state but the
pipeline SHA doesn't match the queue item's expected_sha (e.g. after a rebase
created a new pipeline), the event should be silently ignored.
Covers handlers.py _validate_pipeline_event SHA comparison (lines 557-565).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import PipelineWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_notifier,
    create_mock_queue_manager,
    create_mock_settings,
    create_pipeline_event,
)

MR_IID = 123
EXPECTED_SHA = "abc123def456"
PIPELINE_SHA = "old789sha012"


class Scenario(vedro.Scenario):
    subject = "pipeline event with SHA mismatch is skipped"

    def given_handler_with_sha_mismatch(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()
        # Queue item with expected_sha set (after rebase)
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=QueueItem(
                mr_iid=MR_IID,
                title="Test MR",
                author_name="Author",
                author_username="author",
                target_branch="master",
                state="testing",
                queued_at=datetime.now(UTC),
                pipeline_id=None,
                expected_sha=EXPECTED_SHA,
            )
        )
        self.notifier = create_mock_notifier()
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
        )
        # Pipeline event with a different SHA (old pipeline before rebase)
        self.event = create_pipeline_event(
            mr_iid=MR_IID,
            status="success",
            sha=PIPELINE_SHA,
        )

    async def when_event_is_handled(self):
        with patch("gitlab_queue.webhooks.handlers.create_state_machine_for_mr") as mock_sm:
            mock_state_machine = MagicMock()
            mock_state_machine.trigger_pipeline_success = AsyncMock()
            mock_sm.return_value = mock_state_machine
            await self.handler.handle(self.event)
            self.mock_create_sm = mock_sm
            self.mock_state_machine = mock_state_machine

    def then_queue_item_should_be_checked(self):
        self.queue_manager.get_queue_item.assert_awaited_once_with(MR_IID)

    def and_state_machine_should_not_be_created(self):
        self.mock_create_sm.assert_not_awaited()

    def and_pipeline_success_should_not_be_triggered(self):
        self.mock_state_machine.trigger_pipeline_success.assert_not_awaited()

    def and_mr_state_should_not_be_updated(self):
        self.queue_manager.update_mr_state.assert_not_awaited()

    async def cleanup(self):
        await self.gitlab_client.close()
