"""Test trigger_rebase_failed passes conflict info to context."""

import vedro
from scenarios.library import QueueState
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "trigger_rebase_failed passes conflict info to context"

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
        await self.sm.trigger_rebase_failed(
            conflicted_files=["a.py", "b.py"],
            error_message="Conflict in a.py",
        )

    def then_context_should_contain_failure_reason(self):
        assert self.sm._context.get("failure_reason") == "conflict"

    def and_context_should_contain_conflicted_files(self):
        assert self.sm._context.get("conflicted_files") == ["a.py", "b.py"]

    def and_context_should_contain_error_message(self):
        assert self.sm._context.get("error_message") == "Conflict in a.py"
