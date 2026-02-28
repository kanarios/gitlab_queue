"""BUG-12: unlabeled fallback should use complete_mr, not remove_from_queue."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro
from scenarios.library import Labels
from statemachine.exceptions import TransitionNotAllowed

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import create_mock_settings, create_mr_event

MR_IID = 456


class Scenario(vedro.Scenario):
    subject = "unlabeled fallback uses complete_mr instead of remove_from_queue"

    def given_handler_where_transition_fails(self):
        self.settings = create_mock_settings()

        self.queue_manager = MagicMock()
        self.queue_manager.get_queue_item = AsyncMock(return_value=MagicMock())
        self.queue_manager.remove_from_queue = AsyncMock(return_value=True)
        self.queue_manager.complete_mr = AsyncMock(return_value=True)

        self.gitlab_client = MagicMock()
        self.gitlab_client.remove_mr_label = AsyncMock()

        self.notifier = MagicMock()
        self.notifier.notify = AsyncMock()
        self.notifier.build_pipeline_url = AsyncMock(return_value="")

        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
        )
        # Queue label removed, no hotfix label present -> should_remove = True
        self.event = create_mr_event(
            iid=MR_IID,
            action="unlabeled",
            previous_labels=[Labels.MERGE_QUEUE],
            current_labels=[],
            event_labels=[],
        )

    async def when_unlabeled_event_triggers_transition_not_allowed(self):
        with patch(
            "gitlab_queue.webhooks.handlers.create_state_machine_for_mr",
            new_callable=AsyncMock,
        ) as mock_sm:
            sm = MagicMock()
            sm.current_state.id = "merged"
            sm.trigger_mark_removed = AsyncMock(side_effect=TransitionNotAllowed(MagicMock(), MagicMock()))
            mock_sm.return_value = sm

            await self.handler.handle(self.event)

    def then_complete_mr_should_be_called(self):
        self.queue_manager.complete_mr.assert_awaited_once_with(
            MR_IID,
            status="removed",
            failure_reason="label_removed",
        )

    def and_remove_from_queue_should_not_be_called(self):
        self.queue_manager.remove_from_queue.assert_not_awaited()
