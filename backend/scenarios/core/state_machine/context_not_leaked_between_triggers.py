"""BUG 7: _context should not leak between trigger calls."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "context is not leaked between triggers"

    async def given_state_machine_in_merging_with_residual_context(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.MERGING,
        )
        self.sm._context["pipeline_id"] = 999
        self.sm._context["pipeline_url"] = "https://old-pipeline"

    async def when_merge_failed_is_triggered(self):
        await self.sm.trigger_merge_failed(error_message="Merge rejected")

    def then_stale_pipeline_id_should_not_be_in_context(self):
        assert self.sm._context.get("pipeline_id") != 999, (
            "Stale pipeline_id=999 should not remain in context after trigger_merge_failed"
        )

    def and_stale_pipeline_url_should_not_be_in_context(self):
        assert self.sm._context.get("pipeline_url") != "https://old-pipeline", (
            "Stale pipeline_url should not remain in context after trigger_merge_failed"
        )
