"""Test: canceled pipeline webhook switches to newer pipeline when one exists."""

import vedro
from scenarios.fakes import FakeGitLabClient, FakeStateMachineFactory, create_pipeline

from gitlab_queue.webhooks.handlers import PipelineWebhookHandler

from ._helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_mock_settings,
    create_pipeline_event,
    create_queue_item_in_state,
)

CURRENT_PIPELINE_ID = 1000
NEWER_PIPELINE_ID = 2000
MR_IID = 123
EXPECTED_SHA = "abc123def456"


class Scenario(vedro.Scenario):
    subject = "canceled pipeline switches to newer pipeline when one exists"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.newer_pipeline = create_pipeline(
            id=NEWER_PIPELINE_ID,
            sha=EXPECTED_SHA,
            status="running",
        )
        self.gitlab_client = FakeGitLabClient(
            mr_pipelines_response=[
                create_pipeline(id=CURRENT_PIPELINE_ID, sha=EXPECTED_SHA, status="canceled"),
                self.newer_pipeline,
            ],
        )
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.add_item(
            create_queue_item_in_state(
                "testing",
                mr_iid=MR_IID,
                pipeline_id=CURRENT_PIPELINE_ID,
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
        # Canceled webhook for current pipeline
        self.event = create_pipeline_event(
            mr_iid=MR_IID,
            pipeline_id=CURRENT_PIPELINE_ID,
            status="canceled",
            sha=EXPECTED_SHA,
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_pipeline_id_should_be_switched_to_newer(self):
        switch_calls = [c for c in self.queue_manager.update_state_calls if c.get("pipeline_id") == NEWER_PIPELINE_ID]
        assert len(switch_calls) == 1

    def then_pipeline_should_not_be_marked_failed(self):
        failed_calls = [c for c in self.queue_manager.update_state_calls if c.get("pipeline_status") == "failed"]
        assert len(failed_calls) == 0

    async def cleanup(self):
        await self.gitlab_client.close()
