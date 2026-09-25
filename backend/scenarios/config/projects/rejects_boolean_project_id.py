"""ProjectConfig rejects booleans where an integer project ID is required."""

import vedro
from vedro import catched

from gitlab_queue.config import ProjectConfig, Secret


class Scenario(vedro.Scenario):
    subject = "reject a boolean project ID"

    def when_project_config_is_created(self):
        with catched(ValueError) as self.exception:
            ProjectConfig(project_id=True, token=Secret("token"))

    def then_creation_reports_a_positive_integer_requirement(self):
        assert "positive integer" in str(self.exception.value)
