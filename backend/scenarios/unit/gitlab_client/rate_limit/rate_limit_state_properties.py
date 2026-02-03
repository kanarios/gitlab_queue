"""Test scenario: RateLimitState properties calculate correctly."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import RateLimitState


class Scenario(vedro.Scenario):
    subject = "RateLimitState properties calculate correctly"

    def given_rate_limit_states(self):
        self.state_80_percent = RateLimitState(limit=100, remaining=20)
        self.state_97_percent = RateLimitState(limit=100, remaining=3)
        self.state_unknown = RateLimitState(limit=None, remaining=None)
        self.state_default = RateLimitState()

    def when_properties_are_accessed(self):
        self.ratio_80 = self.state_80_percent.usage_ratio
        self.approaching = self.state_80_percent.is_approaching_limit(0.7)
        self.critical = self.state_97_percent.is_critical(0.95)
        self.ratio_unknown = self.state_unknown.usage_ratio
        self.reset_default = self.state_default.seconds_until_reset

    def then_usage_ratio_should_be_0_8(self):
        assert self.ratio_80 is not None
        assert abs(self.ratio_80 - 0.8) < 1e-9

    def and_is_approaching_limit_should_be_true(self):
        assert self.approaching is True

    def and_is_critical_should_be_true(self):
        assert self.critical is True

    def and_unknown_usage_ratio_should_be_none(self):
        assert self.ratio_unknown is None

    def and_default_seconds_until_reset_should_be_none(self):
        assert self.reset_default is None
