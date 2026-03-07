"""Test scenario: rate limit causes scheduler to pause before sync."""

from __future__ import annotations

from dataclasses import dataclass

import vedro

from gitlab_queue.core.scheduler import QueueScheduler
from scenarios.fakes import FakeGitLabClient, FakeQueueManager, FakeSettings


@dataclass
class CriticalRateLimitState:
    """Rate limit state that is always critical."""

    seconds_until_reset: float = 30.0
    usage_ratio: float = 0.97

    def is_critical(self, _threshold: float) -> bool:
        return True


class Scenario(vedro.Scenario):
    subject = "rate limit at critical level causes scheduler to pause"

    def given_scheduler_with_critical_rate_limit(self):
        self.gitlab_client = FakeGitLabClient(
            rate_limit_state=CriticalRateLimitState(),
        )
        self.settings = FakeSettings()
        self.queue_manager = FakeQueueManager()
        self.scheduler = QueueScheduler(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            settings=self.settings,
        )

    def when_should_pause_is_checked(self):
        self.should_pause, self.pause_seconds = self.scheduler._should_pause_for_rate_limit()

    def then_should_pause_should_be_true(self):
        assert self.should_pause is True

    def and_pause_seconds_should_be_positive(self):
        assert self.pause_seconds > 0

    def and_pause_seconds_should_match_reset_time(self):
        assert self.pause_seconds == 30.0
