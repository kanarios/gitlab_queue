"""Test scenario: rate limit causes scheduler to pause before sync."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import vedro

from gitlab_queue.core.scheduler import QueueScheduler


def create_mock_settings(**overrides: object) -> MagicMock:
    """Create mock Settings for scheduler tests."""
    settings = MagicMock()
    defaults = {
        "queue_label": "merge_queue",
        "hotfix_label": "hotfix",
        "target_branch": "main",
        "poll_interval_seconds": 60,
        "rate_limit_critical_threshold": 0.95,
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(settings, key, value)
    return settings


def create_mock_gitlab_client(is_critical: bool = False) -> MagicMock:
    """Create mock GitLabClient with rate limit state."""
    client = MagicMock()
    rate_limit = MagicMock()
    rate_limit.is_critical.return_value = is_critical
    rate_limit.seconds_until_reset = 30.0
    rate_limit.usage_ratio = 0.97 if is_critical else 0.5
    type(client).rate_limit_state = PropertyMock(return_value=rate_limit)
    client.list_mrs_with_label = AsyncMock(return_value=[])
    return client


def create_mock_queue_manager() -> MagicMock:
    """Create mock QueueManager."""
    qm = MagicMock()
    qm.get_active_queue = AsyncMock(return_value=[])
    qm.get_queue_stats = AsyncMock(return_value={})
    return qm


class Scenario(vedro.Scenario):
    subject = "rate limit at critical level causes scheduler to pause"

    def given_scheduler_with_critical_rate_limit(self):
        self.gitlab_client = create_mock_gitlab_client(is_critical=True)
        self.settings = create_mock_settings()
        self.queue_manager = create_mock_queue_manager()
        self.scheduler = QueueScheduler(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            settings=self.settings,
        )

    def when_should_pause_is_checked(self):
        self.should_pause, self.pause_seconds = self.scheduler._should_pause_for_rate_limit()

    def then_should_pause_should_be_true(self):
        assert self.should_pause is True, (
            f"Expected should_pause=True when rate limit is critical, got {self.should_pause}"
        )

    def and_pause_seconds_should_be_positive(self):
        assert self.pause_seconds > 0, f"Expected positive pause_seconds, got {self.pause_seconds}"

    def and_pause_seconds_should_match_reset_time(self):
        assert self.pause_seconds == 30.0, f"Expected 30.0 seconds until reset, got {self.pause_seconds}"
