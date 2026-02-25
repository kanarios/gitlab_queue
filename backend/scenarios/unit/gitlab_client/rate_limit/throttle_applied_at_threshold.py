"""Test scenario: _apply_rate_limit_throttle adds delay when approaching limit."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro
from scenarios.contexts.gitlab_client_factory import created_test_client
from scenarios.transports import GitLabMockTransport

from gitlab_queue.clients.gitlab import RateLimitState


class Scenario(vedro.Scenario):
    subject = "_apply_rate_limit_throttle adds delay when approaching limit"

    def given_client_with_high_usage(self):
        self.transport = GitLabMockTransport()
        self.client = created_test_client(transport=self.transport)
        # Set 90% usage (above default 80% warning threshold)
        self.client._rate_limit_state = RateLimitState(limit=100, remaining=10)

    async def when_throttle_is_applied(self):
        self.mock_sleep = AsyncMock()
        with patch("asyncio.sleep", self.mock_sleep):
            await self.client._apply_rate_limit_throttle()

    def then_sleep_should_be_called(self):
        self.mock_sleep.assert_awaited_once()

    def and_delay_should_be_positive(self):
        args, _ = self.mock_sleep.await_args
        assert args[0] > 0

    async def do_cleanup(self):
        await self.client.close()
