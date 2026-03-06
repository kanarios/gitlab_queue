"""Test on_enter_failed calls notifier with conflict template."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "on_enter_failed calls notifier with conflict template"

    async def given_state_machine_in_rebasing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.REBASING,
        )

    async def when_rebase_failed_is_triggered(self):
        """
        Trigger a rebase-failed event on the scenario's state machine using a conflict template.

        Calls the state machine's rebase-failed transition with conflicted_files ["src/main.py", "tests/test_main.py"] and error_message "Merge conflict".
        """
        await self.sm.trigger_rebase_failed(
            conflicted_files=["src/main.py", "tests/test_main.py"],
            error_message="Merge conflict",
        )

    def then_notifier_should_be_called_with_conflict_template(self):
        assert len(self.notifier.notify_calls) == 1
        call_args = self.notifier.notify_calls[-1]
        assert call_args["mr_iid"] == 123
        assert call_args["status"] == "conflict"

    def and_notify_should_include_conflicted_files(self):
        call_args = self.notifier.notify_calls[-1]
        assert call_args.get("conflicted_files") == ["src/main.py", "tests/test_main.py"]
