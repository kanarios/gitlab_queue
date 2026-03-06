from __future__ import annotations

from dataclasses import dataclass

import vedro
from scenarios.fakes import FakeCurrentState, FakeStateMachine, FakeStateMachineFactory
from statemachine.exceptions import TransitionNotAllowed

from gitlab_queue.webhooks.handlers import PipelineWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_notifier,
    create_mock_queue_manager,
    create_mock_settings,
    create_pipeline_event,
    create_queue_item_in_state,
)


@dataclass
class _StubState:
    name: str = "stub"
    id: str = "stub"


_STUB = _StubState()


class Scenario(vedro.Scenario):
    subject = "pipeline success catches TransitionNotAllowed"

    def given_handler_and_success_event(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()

        self.queue_manager = create_mock_queue_manager()
        testing_item = create_queue_item_in_state("testing", mr_iid=123)
        # _handle_success re-fetches queue item to detect concurrent state change
        self.queue_manager.get_queue_item_sequence = [testing_item, testing_item]

        self.fake_sm = FakeStateMachine(
            current_state=FakeCurrentState(id="testing"),
            trigger_errors={"pipeline_success": TransitionNotAllowed(_STUB, _STUB)},
        )
        self.sm_factory = FakeStateMachineFactory(state_machine=self.fake_sm)

        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
            state_machine_factory=self.sm_factory,
        )
        self.event = create_pipeline_event(mr_iid=123, status="success")

    async def when_event_is_handled(self):
        self.exc = None
        try:
            await self.handler.handle(self.event)
        except Exception as e:
            self.exc = e

    def then_no_exception_is_propagated(self):
        assert self.exc is None, f"Expected no exception, got: {self.exc!r}"

    async def cleanup(self):
        await self.gitlab_client.close()
