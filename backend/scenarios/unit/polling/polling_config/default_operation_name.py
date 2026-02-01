"""Test PollingConfig has default operation_name of 'polling'."""

import vedro

from gitlab_queue.core.polling import PollingConfig


class Scenario(vedro.Scenario):
    subject = "PollingConfig has default operation_name of 'polling'"

    def given_polling_config_without_operation_name(self):
        self.config = PollingConfig(
            timeout_seconds=60.0,
            poll_interval_seconds=5.0,
        )

    def when_operation_name_is_accessed(self):
        self.operation_name = self.config.operation_name

    def then_operation_name_is_polling(self):
        assert self.operation_name == "polling"
