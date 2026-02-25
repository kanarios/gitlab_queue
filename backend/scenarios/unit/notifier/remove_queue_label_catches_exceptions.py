"""Test remove_queue_label() catches and suppresses exceptions gracefully."""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro

from ._helpers import create_test_notifier


class Scenario(vedro.Scenario):
    subject = "remove_queue_label() catches exception from gitlab_client without propagating"

    def given_notifier_whose_client_raises_on_label_removal(self):
        """
        Set up a notifier whose GitLab client raises an exception when removing a merge request label.
        
        Creates an AsyncMock gitlab_client whose remove_mr_label raises RuntimeError("GitLab API unavailable"), assigns a test notifier configured with that client to `self.notifier`, and sets `self.mr_iid` to 42.
        """
        gitlab_client = AsyncMock()
        gitlab_client.remove_mr_label = AsyncMock(
            side_effect=RuntimeError("GitLab API unavailable"),
        )

        self.notifier = create_test_notifier(gitlab_client=gitlab_client)
        self.mr_iid = 42

    async def when_remove_queue_label_is_called(self):
        # Should complete without raising even though the client raises
        """
        Calls the notifier's remove_queue_label and records whether it raised an exception.
        
        Sets self.raised to True if an exception was raised during the call, otherwise sets it to False.
        """
        self.raised = False
        try:
            await self.notifier.remove_queue_label(self.mr_iid)
        except Exception:
            self.raised = True

    def then_no_exception_is_propagated(self):
        """
        Asserts that no exception was propagated when remove_queue_label was called.
        
        Raises AssertionError if an exception was propagated (i.e., if self.raised is True).
        """
        assert self.raised is False

    def and_gitlab_client_was_called_with_correct_args(self):
        """
        Asserts that the notifier's GitLab client was awaited exactly once to remove the queue label using the scenario's MR IID and the notifier's configured queue label.
        """
        self.notifier.gitlab_client.remove_mr_label.assert_awaited_once_with(
            self.mr_iid,
            self.notifier.settings.queue_label,
        )
