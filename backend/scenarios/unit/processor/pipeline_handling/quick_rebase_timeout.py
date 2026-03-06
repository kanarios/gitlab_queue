"""Test wait_for_rebase_quick raises GitLabAPIError on timeout.

When rebase_in_progress stays True beyond the timeout,
wait_for_rebase_quick should raise a GitLabAPIError indicating
that the rebase operation timed out.
"""

from __future__ import annotations

import asyncio

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError
from gitlab_queue.core.rebase_handler import RebaseHandler
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeSettings

from .._helpers import create_processing_context


class Scenario(vedro.Scenario):
    subject = "wait for rebase quick raises api error on timeout"

    def given_rebase_handler_with_rebase_stuck(self):
        self.gitlab_client = FakeGitLabClient()
        # rebase always in progress, never completes
        self.gitlab_client.rebase_status = (True, False)

        self.handler = RebaseHandler(
            gitlab_client=self.gitlab_client,
            notifier=FakeNotifier(),
            settings=FakeSettings(),
            shutdown_event=asyncio.Event(),
        )

        self.ctx = create_processing_context(mr_iid=42)

    async def when_wait_for_rebase_quick_is_called(self):
        self.raised = None
        try:
            await self.handler.wait_for_rebase_quick(self.ctx)
        except GitLabAPIError as exc:
            self.raised = exc

    def then_api_error_is_raised(self):
        assert self.raised is not None
        assert isinstance(self.raised, GitLabAPIError)

    def and_error_message_mentions_timeout(self):
        assert "timeout" in str(self.raised).lower()
