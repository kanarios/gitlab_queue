"""An empty compose-provided project list follows legacy mode."""

import vedro
from vedro import catched

from gitlab_queue.config import ConfigurationError, load_settings


class Scenario(vedro.Scenario):
    subject = "treat a blank project list as unset"

    def given_environment_with_blank_project_list(self):
        self.env_vars = {
            "GITLAB_QUEUE_PROJECTS": "  \t",
            "GITLAB_QUEUE_JWT_SECRET": "j" * 64,
            "GITLAB_QUEUE_WEBHOOK_SECRET": "webhook-secret",
        }

    def when_settings_are_loaded(self):
        with catched(ConfigurationError) as self.exception:
            load_settings(self.env_vars)

    def then_legacy_credentials_are_required(self):
        assert "gitlab_project_id must be a positive integer" in str(self.exception.value)
        assert "gitlab_token is required" in str(self.exception.value)
