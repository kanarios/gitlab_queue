"""Test scenario: check_rebase_status returns has_conflicts=True when conflicts exist."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_mr

from ._helpers import create_mr_response_for_rebase


class Scenario(vedro.Scenario):
    subject = "check_rebase_status returns has_conflicts=True when conflicts exist"

    async def given_mock_gitlab_with_conflicting_mr(self):
        mr_data = create_mr_response_for_rebase(
            rebase_in_progress=False,
            has_conflicts=True,
        )
        self._mock_ctx = mocked_gitlab_get_mr(TEST_PROJECT_ID, 42, mr_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_check_rebase_status_is_called(self):
        self.in_progress, self.has_conflicts = await self.client.check_rebase_status(42)

    def then_in_progress_should_be_false(self):
        assert self.in_progress is False

    def and_has_conflicts_should_be_true(self):
        assert self.has_conflicts is True

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
