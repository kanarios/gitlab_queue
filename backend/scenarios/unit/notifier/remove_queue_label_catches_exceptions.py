"""Test remove_queue_label() catches and suppresses exceptions gracefully."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

from ._helpers import create_test_notifier


class Scenario(vedro.Scenario):
    subject = "remove_queue_label() catches exception from gitlab_client without propagating"

    def given_notifier_whose_client_raises_on_label_removal(self):
        gitlab_client = AsyncMock()
        gitlab_client.remove_mr_label = AsyncMock(
            side_effect=RuntimeError("GitLab API unavailable"),
        )
        note = MagicMock()
        note.id = 1
        gitlab_client.add_or_update_pinned_comment.return_value = note

        self.notifier = create_test_notifier(gitlab_client=gitlab_client)
        self.mr_iid = 42

    async def when_remove_queue_label_is_called(self):
        # Should complete without raising even though the client raises
        self.raised = False
        try:
            await self.notifier.remove_queue_label(self.mr_iid)
        except Exception:
            self.raised = True

    def then_no_exception_is_propagated(self):
        assert self.raised is False

    def and_gitlab_client_was_called_with_correct_args(self):
        self.notifier.gitlab_client.remove_mr_label.assert_called_once_with(
            self.mr_iid,
            self.notifier.settings.queue_label,
        )
