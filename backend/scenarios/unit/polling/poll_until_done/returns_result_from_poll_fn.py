"""Test poll_until_done returns result from poll_fn."""

import vedro

from gitlab_queue.core.polling import poll_until_done

from .._helpers import (
    create_immediate_done_poll_fn,
    create_polling_config,
    create_shutdown_event,
)


class Scenario(vedro.Scenario):
    subject = "poll_until_done returns result from poll_fn"

    def given_config_and_poll_fn_with_result(self):
        self.expected_result = {"status": "success", "data": 123}
        self.config = create_polling_config()
        self.poll_fn = create_immediate_done_poll_fn(result=self.expected_result)
        self.shutdown_event = create_shutdown_event()

    async def when_poll_until_done_is_called(self):
        self.outcome = await poll_until_done(
            self.config,
            self.poll_fn,
            self.shutdown_event,
        )

    def then_result_matches_expected(self):
        assert self.outcome.result == self.expected_result
