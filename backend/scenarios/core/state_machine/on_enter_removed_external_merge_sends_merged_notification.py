"""Test on_enter_removed with external_merge sends merged notification."""

from __future__ import annotations

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "on_enter_removed with external_merge sends merged notification"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
        )

    async def when_mark_removed_is_triggered_with_external_merge(self):
        await self.sm.trigger_mark_removed(reason="external_merge")

    def then_notifier_receives_merged_status(self):
        assert len(self.notifier.notify_calls) == 1
        call_args = self.notifier.notify_calls[0]
        assert call_args["mr_iid"] == 123
        assert call_args["status"] == "merged"

    def and_notify_includes_duration(self):
        call_args = self.notifier.notify_calls[0]
        assert "duration" in call_args

    def and_notify_includes_target_branch(self):
        call_args = self.notifier.notify_calls[0]
        assert "target_branch" in call_args

    def and_history_status_is_merged(self):
        assert len(self.queue_manager.complete_calls) == 1
        assert self.queue_manager.complete_calls[0]["status"] == "merged"

    def and_label_is_not_removed_again(self):
        assert self.notifier.remove_label_calls == []
