"""Test poll_until_done returns shutdown_requested=True when event set."""

import vedro

from gitlab_queue.core.polling import poll_until_done

from .._helpers import (
    create_never_done_poll_fn,
    create_polling_config,
    create_shutdown_event,
)


class Scenario(vedro.Scenario):
    subject = "poll_until_done returns shutdown_requested=True when event set"

    def given_config_and_set_shutdown_event(self):
        self.config = create_polling_config()
        self.poll_fn = create_never_done_poll_fn()
        self.shutdown_event = create_shutdown_event(is_set=True)

    async def when_poll_until_done_is_called(self):
        self.outcome = await poll_until_done(
            self.config,
            self.poll_fn,
            self.shutdown_event,
        )

    def then_shutdown_requested_is_true(self):
        assert self.outcome.shutdown_requested is True

    def and_completed_is_false(self):
        assert self.outcome.completed is False

    def and_timed_out_is_false(self):
        assert self.outcome.timed_out is False
