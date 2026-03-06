"""Test scenario: request_shutdown stops the scheduler gracefully."""

from __future__ import annotations

import vedro

from gitlab_queue.core.scheduler import QueueScheduler
from scenarios.fakes import FakeGitLabClient, FakeQueueManager, FakeSettings


class Scenario(vedro.Scenario):
    subject = "request_shutdown sets shutdown event and stops scheduler"

    def given_running_scheduler(self):
        self.scheduler = QueueScheduler(
            gitlab_client=FakeGitLabClient(),
            queue_manager=FakeQueueManager(),
            settings=FakeSettings(),
        )

    def when_shutdown_is_requested(self):
        self.scheduler.request_shutdown()

    def then_shutdown_should_be_requested(self):
        assert self.scheduler.is_shutdown_requested is True

    def and_shutdown_event_should_be_set(self):
        assert self.scheduler._shutdown_event.is_set() is True
