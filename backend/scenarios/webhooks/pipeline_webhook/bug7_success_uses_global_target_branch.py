"""BUG-7: Pipeline handler uses global target_branch instead of queue item's."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.webhooks.handlers import PipelineWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_notifier,
    create_mock_queue_manager,
    create_mock_settings,
    create_pipeline_event,
    create_queue_item_in_state,
)


class Scenario(vedro.Scenario):
    subject = "pipeline success uses queue item target_branch not global"

    def given_handler_with_different_target_branches(self):
        self.settings = create_mock_settings()
        self.settings.target_branch = "master"  # global setting

        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()

        # Create queue item with different target_branch
        self.testing_item = create_queue_item_in_state("testing", mr_iid=123)
        self.testing_item.target_branch = "release/1.0"  # per-MR setting
        self.queue_manager.get_queue_item = AsyncMock(
            side_effect=[self.testing_item, self.testing_item],
        )

        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
        )
        self.event = create_pipeline_event(mr_iid=123, status="success")

    async def when_success_event_is_handled(self):
        with patch(
            "gitlab_queue.webhooks.handlers.create_state_machine_for_mr",
            new_callable=AsyncMock,
        ) as self.mock_create_sm:
            sm = MagicMock()
            sm.trigger_pipeline_success = AsyncMock()
            self.mock_create_sm.return_value = sm

            await self.handler.handle(self.event)

    def then_state_machine_created_with_queue_item_target_branch(self):
        call_kwargs = self.mock_create_sm.call_args.kwargs
        assert call_kwargs["target_branch"] == "release/1.0", (
            f"Expected target_branch='release/1.0', got '{call_kwargs['target_branch']}'"
        )

    async def cleanup(self):
        await self.gitlab_client.close()
