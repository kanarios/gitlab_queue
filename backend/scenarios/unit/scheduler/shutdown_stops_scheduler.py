"""Test scenario: request_shutdown stops the scheduler gracefully."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

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


class Scenario(vedro.Scenario):
    subject = "request_shutdown sets shutdown event and stops scheduler"

    def given_running_scheduler(self):
        gitlab_client = MagicMock()
        rate_limit = MagicMock()
        rate_limit.is_critical.return_value = False
        type(gitlab_client).rate_limit_state = PropertyMock(return_value=rate_limit)

        queue_manager = MagicMock()
        settings = create_mock_settings()
        self.scheduler = QueueScheduler(
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            settings=settings,
        )

    def when_shutdown_is_requested(self):
        self.scheduler.request_shutdown()

    def then_shutdown_should_be_requested(self):
        assert self.scheduler.is_shutdown_requested is True

    def and_shutdown_event_should_be_set(self):
        assert self.scheduler._shutdown_event.is_set() is True
