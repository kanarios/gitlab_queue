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
        """
        Prepare a test GitLab client whose rate limit is at 90% usage.
        
        Creates a GitLabMockTransport-backed test client and sets its internal RateLimitState to limit=100 and remaining=10 (i.e., 90% consumed) so throttling logic treats the client as approaching the rate limit.
        """
        self.transport = GitLabMockTransport()
        self.client = created_test_client(transport=self.transport)
        # Set 90% usage (above default 80% warning threshold)
        self.client._rate_limit_state = RateLimitState(limit=100, remaining=10)

    async def when_throttle_is_applied(self):
        """
        Patches asyncio.sleep with an AsyncMock and invokes the client's rate-limit throttle to exercise its sleep-based backoff.
        
        This step replaces asyncio.sleep with a mock to capture calls, then awaits self.client._apply_rate_limit_throttle() so the test can assert that a delay was scheduled.
        """
        self.mock_sleep = AsyncMock()
        with patch("asyncio.sleep", self.mock_sleep):
            await self.client._apply_rate_limit_throttle()

    def then_sleep_should_be_called(self):
        """
        Asserts that the patched asyncio.sleep was awaited exactly once.
        """
        self.mock_sleep.assert_awaited_once()

    def and_delay_should_be_positive(self):
        """
        Asserts that the throttle delay passed to the mocked sleep is greater than zero.
        
        Retrieves the first positional argument from the recorded await call to the mocked sleep and verifies it is > 0.
        """
        args, _ = self.mock_sleep.await_args
        assert args[0] > 0

    async def do_cleanup(self):
        """
        Close the test client created for the scenario, releasing any associated resources.
        """
        await self.client.close()
