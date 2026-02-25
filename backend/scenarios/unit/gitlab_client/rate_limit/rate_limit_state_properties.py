"""Test scenario: RateLimitState properties calculate correctly."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import RateLimitState


class Scenario(vedro.Scenario):
    subject = "RateLimitState properties calculate correctly"

    def given_rate_limit_states(self):
        """
        Prepare several RateLimitState instances used by the scenario.
        
        Creates:
            - self.state_80_percent: RateLimitState with limit=100 and remaining=20 (80% usage).
            - self.state_97_percent: RateLimitState with limit=100 and remaining=3 (97% usage).
            - self.state_unknown: RateLimitState with limit=None and remaining=None (unknown values).
            - self.state_default: RateLimitState constructed with default arguments.
        """
        self.state_80_percent = RateLimitState(limit=100, remaining=20)
        self.state_97_percent = RateLimitState(limit=100, remaining=3)
        self.state_unknown = RateLimitState(limit=None, remaining=None)
        self.state_default = RateLimitState()

    def when_properties_are_accessed(self):
        """
        Access several computed properties from the prepared RateLimitState instances and store them on self for later assertions.
        
        Sets the following attributes:
        - ratio_80: usage_ratio of self.state_80_percent
        - approaching: result of self.state_80_percent.is_approaching_limit(0.7)
        - critical: result of self.state_97_percent.is_critical(0.95)
        - ratio_unknown: usage_ratio of self.state_unknown
        - reset_default: seconds_until_reset of self.state_default
        """
        self.ratio_80 = self.state_80_percent.usage_ratio
        self.approaching = self.state_80_percent.is_approaching_limit(0.7)
        self.critical = self.state_97_percent.is_critical(0.95)
        self.ratio_unknown = self.state_unknown.usage_ratio
        self.reset_default = self.state_default.seconds_until_reset

    def then_usage_ratio_should_be_0_8(self):
        """
        Asserts that the scenario's usage_ratio equals 0.8 within a 1e-9 tolerance.
        
        Raises:
            AssertionError: If `self.ratio_80` is None or its absolute difference from 0.8 is greater than or equal to 1e-9.
        """
        assert self.ratio_80 is not None
        assert abs(self.ratio_80 - 0.8) < 1e-9

    def and_is_approaching_limit_should_be_true(self):
        """
        Asserts that the rate limit state is considered to be approaching the configured threshold.
        
        Verifies that the previously computed `self.approaching` value is `True`.
        """
        assert self.approaching is True

    def and_is_critical_should_be_true(self):
        """
        Asserts that the evaluated RateLimitState is in a critical condition.
        """
        assert self.critical is True

    def and_unknown_usage_ratio_should_be_none(self):
        """
        Asserts that the usage ratio is unavailable (None) for a rate limit state with unknown values.
        """
        assert self.ratio_unknown is None

    def and_default_seconds_until_reset_should_be_none(self):
        assert self.reset_default is None
