"""Test: notify_rebase_during_testing updates expected_sha in context and DB.

Bug: when target branch changes during testing, rebase produces a new SHA,
but notify_rebase_during_testing() didn't propagate expected_sha to the
queue manager or internal context. This caused pipeline_handler to compare
against the old SHA.
"""

from __future__ import annotations

import vedro

from ._helpers import create_mock_notifier, create_mock_queue_manager, create_state_machine


class Scenario(vedro.Scenario):
    subject = "notify_rebase_during_testing updates expected_sha"

    async def given_state_machine_in_testing_state(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = create_state_machine(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
        )
        await self.sm.trigger_start_processing()
        await self.sm.trigger_rebase_complete(
            pipeline_id=100,
            pipeline_url="https://gitlab.com/pipeline/100",
            expected_sha="old_sha_abc",
        )
        self.queue_manager.update_state_calls.clear()

    async def when_notify_rebase_during_testing_is_called_with_expected_sha(self):
        await self.sm.notify_rebase_during_testing(
            old_pipeline_id=100,
            new_pipeline_id=200,
            rebase_count=1,
            max_attempts=3,
            expected_sha="new_sha_abc",
        )

    def then_queue_manager_receives_expected_sha(self):
        call = self.queue_manager.update_state_calls[-1]
        assert call.get("expected_sha") == "new_sha_abc"
