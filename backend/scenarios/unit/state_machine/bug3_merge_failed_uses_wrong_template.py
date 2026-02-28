"""BUG-3: Merge timeout sends 'pipeline_failed' notification instead of 'timeout'."""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro

from gitlab_queue.core.state_machine import MRStateMachine

from ._helpers import MockQueueItem, create_mock_notifier, create_mock_queue_manager


class Scenario(vedro.Scenario):
    subject = "trigger_merge_failed sends merge_failed notification not pipeline_failed"

    def given_state_machine_in_merging_state(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=MockQueueItem(mr_iid=42),
        )

        self.sm = MRStateMachine(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
            mr_iid=42,
            start_value="merging",
            skip_initial_enter=True,
        )

    async def when_merge_failed_is_triggered(self):
        await self.sm.activate_initial_state()
        await self.sm.trigger_merge_failed(error_message="Merge timed out after 120s")

    def then_notifier_should_use_merge_failed_template(self):
        template = self.notifier.notify.call_args.args[1]
        assert template == "merge_failed", f"Expected 'merge_failed' template, got '{template}'"

    def and_notifier_should_not_use_pipeline_failed_template(self):
        template = self.notifier.notify.call_args.args[1]
        assert template != "pipeline_failed"
