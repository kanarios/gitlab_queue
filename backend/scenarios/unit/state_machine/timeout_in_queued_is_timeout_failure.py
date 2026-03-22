"""Timeout from 'queued' should be treated as timeout failure (not removal)."""

from __future__ import annotations

from datetime import UTC, datetime

import vedro

from gitlab_queue.core.state_machine import MRStateMachine
from gitlab_queue.models.queue_item import QueueItem

from ._helpers import create_mock_notifier, create_mock_queue_manager


class Scenario(vedro.Scenario):
    subject = "trigger_timeout from queued state notifies timeout and stores timeout in history"

    def given_state_machine_in_queued_state(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()

        queue_item = QueueItem(
            mr_iid=42,
            title="Test MR",
            author_name="Test",
            author_username="test",
            target_branch="main",
            state="queued",
            queued_at=datetime.now(UTC),
        )
        self.queue_manager.add_item(queue_item)

        self.sm = MRStateMachine(
            notifier=self.notifier,
            queue_manager=self.queue_manager,
            project_id=99999,
            mr_iid=42,
            start_value="queued",
            skip_initial_enter=True,
        )

    async def when_timeout_is_triggered(self):
        await self.sm.activate_initial_state()
        await self.sm.trigger_timeout(max_wait_hours=2)

    def then_timeout_notification_is_sent(self):
        assert len(self.notifier.notify_calls) == 1
        assert self.notifier.notify_calls[0]["mr_iid"] == 42
        assert self.notifier.notify_calls[0]["status"] == "timeout"

    def and_history_status_is_timeout(self):
        assert len(self.queue_manager.complete_calls) >= 1
        assert self.queue_manager.complete_calls[-1]["status"] == "timeout"
