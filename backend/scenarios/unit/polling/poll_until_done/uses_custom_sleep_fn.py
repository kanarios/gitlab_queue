"""Test poll_until_done uses custom sleep function."""

import vedro

from gitlab_queue.core.polling import poll_until_done

from .._helpers import (
    create_counting_poll_fn,
    create_instant_sleep_fn,
    create_polling_config,
    create_shutdown_event,
)


class Scenario(vedro.Scenario):
    subject = "poll_until_done uses custom sleep function"

    def given_config_and_tracking_sleep_fn(self):
        self.config = create_polling_config(
            timeout_seconds=60,
            poll_interval_seconds=5.0,
        )
        self.poll_fn, _ = create_counting_poll_fn(done_after=3)
        self.shutdown_event = create_shutdown_event()
        self.sleep_fn, self.sleep_durations = create_instant_sleep_fn()

    async def when_poll_until_done_is_called(self):
        self.outcome = await poll_until_done(
            self.config,
            self.poll_fn,
            self.shutdown_event,
            sleep_fn=self.sleep_fn,
        )

    def then_sleep_was_called_with_poll_interval(self):
        assert 5.0 in self.sleep_durations

    def and_sleep_was_called_twice(self):
        assert len(self.sleep_durations) == 2
