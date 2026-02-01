"""Test poll_until_done returns timed_out=True when timeout exceeded."""

import vedro

from gitlab_queue.core.polling import poll_until_done

from .._helpers import (
    create_instant_sleep_fn,
    create_never_done_poll_fn,
    create_polling_config,
    create_shutdown_event,
)


class Scenario(vedro.Scenario):
    subject = "poll_until_done returns timed_out=True when timeout exceeded"

    def given_config_with_zero_timeout(self):
        self.config = create_polling_config(timeout_seconds=0)
        self.poll_fn = create_never_done_poll_fn()
        self.shutdown_event = create_shutdown_event()
        self.sleep_fn, _ = create_instant_sleep_fn()

    async def when_poll_until_done_is_called(self):
        self.outcome = await poll_until_done(
            self.config,
            self.poll_fn,
            self.shutdown_event,
            sleep_fn=self.sleep_fn,
        )

    def then_timed_out_is_true(self):
        assert self.outcome.timed_out is True

    def and_completed_is_false(self):
        assert self.outcome.completed is False

    def and_shutdown_requested_is_false(self):
        assert self.outcome.shutdown_requested is False
