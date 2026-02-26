"""Test scenario: notify_rebase_during_testing calls notifier with correct template."""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro

from ._helpers import create_mock_notifier, create_mock_queue_manager, create_state_machine


class Scenario(vedro.Scenario):
    subject = "notify_rebase_during_testing updates state and notifies"

    def given_state_machine_in_testing_state(self):
        self.notifier = create_mock_notifier()
        self.notifier.build_pipeline_url = AsyncMock(return_value="https://gitlab.com/pipeline/200")
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
        # Reset mocks to only capture the call we care about
        self.notifier.notify.reset_mock()
        self.queue_manager.update_mr_state.reset_mock()

        await self.sm.notify_rebase_during_testing(
            old_pipeline_id=100,
            new_pipeline_id=200,
            rebase_count=1,
            max_attempts=3,
        )

    def then_queue_manager_should_update_pipeline(self):
        self.queue_manager.update_mr_state.assert_awaited_once_with(
            42,
            "testing",
            pipeline_id=200,
            pipeline_status="running",
        )

    def and_notifier_should_be_called_with_rebase_during_testing_template(self):
        self.notifier.notify.assert_awaited_once()
        call_args = self.notifier.notify.call_args
        assert call_args.args[1] == "rebase_during_testing"

    def and_notification_should_include_pipeline_ids(self):
        call_kwargs = self.notifier.notify.call_args.kwargs
        assert call_kwargs["old_pipeline_id"] == 100
        assert call_kwargs["pipeline_id"] == 200
        assert call_kwargs["rebase_count"] == 1
        assert call_kwargs["max_attempts"] == 3

    def and_context_should_be_updated_with_new_pipeline(self):
        assert self.sm._context["pipeline_id"] == 200
        assert self.sm._context["pipeline_url"] == "https://gitlab.com/pipeline/200"
