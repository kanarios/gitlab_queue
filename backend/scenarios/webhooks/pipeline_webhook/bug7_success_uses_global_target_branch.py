"""BUG-7: Pipeline handler uses global target_branch instead of queue item's."""

from __future__ import annotations

import vedro
from scenarios.fakes import FakeCurrentState, FakeStateMachine, FakeStateMachineFactory

from gitlab_queue.webhooks.handlers import PipelineWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_notifier,
    create_mock_queue_manager,
    create_mock_settings,
    create_pipeline_event,
    create_queue_item_in_state,
)


class Scenario(vedro.Scenario):
    subject = "pipeline success uses queue item target_branch not global"

    def given_handler_with_different_target_branches(self):
        self.settings = create_mock_settings()
        self.settings.target_branch = "master"  # global setting

        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()

        # Create queue item with different target_branch
        self.testing_item = create_queue_item_in_state("testing", mr_iid=123)
        self.testing_item.target_branch = "release/1.0"  # per-MR setting
        self.queue_manager.get_queue_item_sequence = [self.testing_item, self.testing_item]

        self.fake_sm = FakeStateMachine(current_state=FakeCurrentState(id="testing"))
        self.sm_factory = FakeStateMachineFactory(state_machine=self.fake_sm)

        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
            state_machine_factory=self.sm_factory,
        )
        self.event = create_pipeline_event(mr_iid=123, status="success")

    async def when_success_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_state_machine_created_with_queue_item_target_branch(self):
        assert len(self.sm_factory.calls) == 1
        call_kwargs = self.sm_factory.calls[0]
        assert call_kwargs["target_branch"] == "release/1.0", (
            f"Expected target_branch='release/1.0', got '{call_kwargs['target_branch']}'"
        )

    async def cleanup(self):
        await self.gitlab_client.close()
