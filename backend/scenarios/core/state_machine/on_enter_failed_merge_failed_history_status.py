"""BUG 3: merge_failed should record history status as merge_failed, not timeout."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "on_enter_failed with merge_failed records merge_failed in history"

    async def given_state_machine_in_merging(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.MERGING,
        )

    async def when_merge_failed_is_triggered(self):
        await self.sm.trigger_merge_failed(error_message="Merge rejected")

    def then_history_status_should_be_merge_failed(self):
        self.queue_manager.complete_mr.assert_awaited()
        kwargs = self.queue_manager.complete_mr.call_args.kwargs
        assert kwargs["status"] == "merge_failed", f"Expected history status 'merge_failed', got '{kwargs['status']}'"

    def and_history_status_should_not_be_timeout(self):
        kwargs = self.queue_manager.complete_mr.call_args.kwargs
        assert kwargs["status"] != "timeout", "merge_failed should not record timeout in history"
