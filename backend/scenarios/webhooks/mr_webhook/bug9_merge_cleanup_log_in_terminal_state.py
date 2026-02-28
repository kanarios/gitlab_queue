"""Test: _handle_merge does NOT log 'cleaned up' for terminal state MR."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro
from scenarios.webhooks.pipeline_webhook._helpers import create_queue_item_in_state

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_mock_queue_manager,
    create_mock_settings,
    create_mr_event,
)


class Scenario(vedro.Scenario):
    subject = "_handle_merge does not log 'MR cleaned up' when MR is in terminal state"

    def given_handler_with_terminal_state_mr(self):
        self.settings = create_mock_settings()
        self.gitlab_client = MagicMock()
        self.queue_manager = create_mock_queue_manager()
        self.queue_item = create_queue_item_in_state("merged", mr_iid=123)
        self.queue_manager.get_queue_item = AsyncMock(return_value=self.queue_item)

        self.notifier = MagicMock()
        self.notifier.notify = AsyncMock()
        self.notifier.remove_queue_label = AsyncMock()

        # Mock create_state_machine_for_mr to return SM in terminal state
        self.mock_sm = MagicMock()
        self.mock_sm.current_state = MagicMock()
        self.mock_sm.current_state.id = "merged"

        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
        )

        self.event = create_mr_event(iid=123, action="merge", state="merged")

    async def when_merge_event_is_handled(self):
        with (
            patch(
                "gitlab_queue.webhooks.handlers.create_state_machine_for_mr",
                new=AsyncMock(return_value=self.mock_sm),
            ),
            patch("gitlab_queue.webhooks.handlers.log") as self.mock_log,
        ):
            self.mock_log.debug = MagicMock()
            self.mock_log.info = MagicMock()
            self.mock_log.warning = MagicMock()
            await self.handler._handle_merge(self.event)

    def then_cleanup_message_should_not_be_logged(self):
        for level in ("debug", "info", "warning"):
            log_method = getattr(self.mock_log, level)
            for call in log_method.call_args_list:
                msg = str(call.args[0]) if call.args else ""
                assert "cleaned up" not in msg.lower(), (
                    f"Unexpected 'cleaned up' log at {level} level for terminal state MR: {call}"
                )
