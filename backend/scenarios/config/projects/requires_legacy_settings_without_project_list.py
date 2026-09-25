"""Legacy mode still requires both GitLab project credentials."""

import vedro
from vedro import catched

from gitlab_queue.config import ConfigurationError, load_settings


class Scenario(vedro.Scenario):
    subject = "require legacy GitLab settings when project list is absent"

    def given_environment_without_gitlab_project_settings(self):
        self.env_vars = {
            "GITLAB_QUEUE_JWT_SECRET": "j" * 64,
            "GITLAB_QUEUE_WEBHOOK_SECRET": "webhook-secret",
        }

    def when_settings_are_loaded(self):
        with catched(ConfigurationError) as self.exception:
            load_settings(self.env_vars)

    def then_error_mentions_both_required_fields(self):
        assert "gitlab_project_id must be a positive integer" in str(self.exception.value)
        assert "gitlab_token is required" in str(self.exception.value)
