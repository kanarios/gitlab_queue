"""BUG 1 fix verification: conflict during testing uses pipeline_failed transition."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "conflict during testing transitions to failed with conflict template"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.TESTING,
        )

    async def when_trigger_conflict_during_testing_is_called(self):
        await self.sm.trigger_conflict_during_testing(
            conflicted_files=["file.py"],
            error_message="Conflict detected during testing",
        )

    def then_state_should_be_failed(self):
        assert self.sm.current_state.id == "failed"

    def then_notifier_called_with_conflict_template(self):
        assert len(self.notifier.notify_calls) >= 1
        assert self.notifier.notify_calls[-1]["status"] == "conflict"
