"""Test scenario: _apply_rate_limit_throttle adds delay when approaching limit."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabClient, RateLimitState
from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.transports import GitLabMockTransport


class _RecordingSleepFn:
    """Async sleep function that records calls."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.calls.append(delay)


class Scenario(vedro.Scenario):
    subject = "_apply_rate_limit_throttle adds delay when approaching limit"

    def given_client_with_high_usage(self):
        self.transport = GitLabMockTransport()
        self.sleep_fn = _RecordingSleepFn()
        settings = created_test_settings()
        self.client = GitLabClient(settings, transport=self.transport, sleep_fn=self.sleep_fn)
        # Set 90% usage (above default 80% warning threshold)
        self.client._rate_limit_state = RateLimitState(limit=100, remaining=10)

    async def when_throttle_is_applied(self):
        await self.client._apply_rate_limit_throttle()

    def then_sleep_should_be_called(self):
        assert len(self.sleep_fn.calls) == 1

    def and_delay_should_be_positive(self):
        assert self.sleep_fn.calls[0] > 0

    async def do_cleanup(self):
        await self.client.close()
