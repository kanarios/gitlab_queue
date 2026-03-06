"""Test: pipeline event with SHA mismatch is skipped.

When a pipeline webhook event arrives for an MR in testing state but the
pipeline SHA doesn't match the queue item's expected_sha (e.g. after a rebase
created a new pipeline), the event should be silently ignored.
"""

from __future__ import annotations

from datetime import UTC, datetime

import vedro
from scenarios.fakes import FakeStateMachineFactory

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
        self.queue_manager.add_item(
            QueueItem(
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

        self.sm_factory = FakeStateMachineFactory()

        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
            state_machine_factory=self.sm_factory,
        )
        # Pipeline event with a different SHA (old pipeline before rebase)
        self.event = create_pipeline_event(
            mr_iid=MR_IID,
            status="success",
            sha=PIPELINE_SHA,
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_queue_item_should_be_checked(self):
        assert MR_IID in self.queue_manager.get_queue_item_calls

    def and_state_machine_should_not_be_created(self):
        assert self.sm_factory.calls == []

    def and_mr_state_should_not_be_updated(self):
        assert self.queue_manager.update_state_calls == []

    async def cleanup(self):
        await self.gitlab_client.close()
