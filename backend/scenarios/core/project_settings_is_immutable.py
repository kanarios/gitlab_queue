"""Project settings views cannot be modified after creation."""

from dataclasses import FrozenInstanceError

import vedro
from vedro import catched

from gitlab_queue.config import ProjectConfig, Secret, Settings
from gitlab_queue.core.project_components import ProjectSettings


class Scenario(vedro.Scenario):
    subject = "keep project settings immutable"

    def given_project_settings_view(self):
        settings = Settings(
            gitlab_token=Secret("legacy-token"),
            gitlab_project_id=3,
            jwt_secret=Secret("j" * 64),
        )
        project = ProjectConfig(project_id=17, token=Secret("project-token"))
        self.project_settings = ProjectSettings(config=project, application=settings)

    def when_project_settings_are_modified(self):
        with catched(FrozenInstanceError) as self.exception:
            self.project_settings.queue_label = "changed"

    def then_the_view_rejects_mutation(self):
        assert self.exception.type is FrozenInstanceError
