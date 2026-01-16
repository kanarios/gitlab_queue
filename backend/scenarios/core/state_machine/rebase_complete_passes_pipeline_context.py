"""Test trigger_rebase_complete passes pipeline info to context."""

import vedro
from scenarios.library import QueueState
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "trigger_rebase_complete passes pipeline info to context"

    async def given_state_machine_in_rebasing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.REBASING,
        )

    async def when_rebase_complete_is_triggered(self):
        await self.sm.trigger_rebase_complete(
            pipeline_id=789,
            pipeline_url="https://gitlab.com/pipeline/789",
        )

    def then_context_should_contain_pipeline_info(self):
        assert self.sm._context.get("pipeline_id") == 789
        assert self.sm._context.get("pipeline_url") == "https://gitlab.com/pipeline/789"
