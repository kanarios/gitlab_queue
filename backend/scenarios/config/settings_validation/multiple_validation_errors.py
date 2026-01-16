"""Test validation collects multiple errors."""

import vedro

from gitlab_queue.config import ConfigurationError, _validate_settings

from ._helpers import create_valid_settings


class Scenario(vedro.Scenario):
    subject = "validation collects multiple errors"

    def given_settings_with_multiple_issues(self):
        self.settings = create_valid_settings(
            gitlab_project_id=-1,
            poll_interval_seconds=0,
            webhook_port=99999,
        )

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_report_all_errors(self):
        assert self.error is not None
        error_msg = str(self.error)
        assert "gitlab_project_id" in error_msg
        assert "poll_interval_seconds" in error_msg
        assert "webhook_port" in error_msg
