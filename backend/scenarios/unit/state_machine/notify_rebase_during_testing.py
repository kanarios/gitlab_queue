"""Test scenario: notify_rebase_during_testing calls notifier with correct template."""

from __future__ import annotations

import vedro

from ._helpers import create_mock_notifier, create_mock_queue_manager, create_state_machine


class Scenario(vedro.Scenario):
    subject = "notify_rebase_during_testing updates state and notifies"

    def given_state_machine_in_testing_state(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = create_state_machine(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
        )
        # Advance to testing state through proper transitions
        self.sm._context = {
            "pipeline_id": 100,
            "pipeline_url": "https://gitlab.com/pipeline/100",
        }

    async def when_notify_rebase_during_testing_is_called(self):
        # First advance to testing state
        await self.sm.trigger_start_processing()
        await self.sm.trigger_rebase_complete(
            pipeline_id=100,
            pipeline_url="https://gitlab.com/pipeline/100",
        )
        # Clear recorded calls to only capture the call we care about
        self.notifier.notify_calls.clear()
        self.queue_manager.update_state_calls.clear()

        await self.sm.notify_rebase_during_testing(
            old_pipeline_id=100,
            new_pipeline_id=200,
            rebase_count=1,
            max_attempts=3,
        )

    def then_queue_manager_should_update_pipeline(self):
        assert len(self.queue_manager.update_state_calls) == 1
        call = self.queue_manager.update_state_calls[0]
        assert call["mr_iid"] == 42
        assert call["state"] == "testing"
        assert call["pipeline_id"] == 200
        assert call["pipeline_status"] == "running"

    def and_notifier_should_be_called_with_rebase_during_testing_template(self):
        assert len(self.notifier.notify_calls) == 1
        assert self.notifier.notify_calls[0]["status"] == "rebase_during_testing"

    def and_notification_should_include_pipeline_ids(self):
        call = self.notifier.notify_calls[0]
        assert call["old_pipeline_id"] == 100
        assert call["pipeline_id"] == 200
        assert call["rebase_count"] == 1
        assert call["max_attempts"] == 3

    def and_context_should_be_updated_with_new_pipeline(self):
        assert self.sm._context["pipeline_id"] == 200
        assert self.sm._context["pipeline_url"] == "https://gitlab.com/pipeline/200"
