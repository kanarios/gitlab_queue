"""ProjectConfig requires non-empty per-project labels."""

import vedro
from vedro import catched

from gitlab_queue.config import ProjectConfig, Secret


class Scenario(vedro.Scenario):
    subject = "reject a blank queue label"

    def when_project_config_is_created(self):
        with catched(ValueError) as self.exception:
            ProjectConfig(project_id=17, token=Secret("token"), queue_label=" ")

    def then_creation_reports_a_non_empty_string_requirement(self):
        assert "queue_label must be a non-empty string" in str(self.exception.value)
