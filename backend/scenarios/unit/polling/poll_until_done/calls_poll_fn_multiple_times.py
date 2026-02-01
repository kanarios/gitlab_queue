"""Test poll_until_done calls poll_fn until DONE."""

import vedro

from gitlab_queue.core.polling import poll_until_done

from .._helpers import (
    create_counting_poll_fn,
    create_instant_sleep_fn,
    create_polling_config,
    create_shutdown_event,
)


class Scenario(vedro.Scenario):
    subject = "poll_until_done calls poll_fn until DONE"

    def given_config_and_counting_poll_fn(self):
        self.config = create_polling_config(timeout_seconds=60)
        self.poll_fn, self.counter = create_counting_poll_fn(done_after=3)
        self.shutdown_event = create_shutdown_event()
        self.sleep_fn, _ = create_instant_sleep_fn()

    async def when_poll_until_done_is_called(self):
        self.outcome = await poll_until_done(
            self.config,
            self.poll_fn,
            self.shutdown_event,
            sleep_fn=self.sleep_fn,
        )

    def then_poll_fn_was_called_three_times(self):
        assert self.counter[0] == 3

    def and_completed_is_true(self):
        assert self.outcome.completed is True
