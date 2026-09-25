"""Project settings view combines project-specific and shared values."""

import vedro

from gitlab_queue.config import ProjectConfig, Secret, Settings
from gitlab_queue.core.project_components import ProjectSettings


class Scenario(vedro.Scenario):
    subject = "provide project-scoped and shared settings together"

    def given_global_settings_and_project_config(self):
        self.global_settings = Settings(
            gitlab_token=Secret("legacy-token"),
            gitlab_project_id=3,
            jwt_secret=Secret("j" * 64),
            poll_interval_seconds=12,
        )
        self.project = ProjectConfig(
            project_id=17,
            token=Secret("project-token"),
            target_branch="main",
            queue_label="team-queue",
            hotfix_label="urgent",
        )

    def when_project_settings_view_is_created(self):
        self.settings = ProjectSettings(config=self.project, application=self.global_settings)

    def then_project_values_override_legacy_values(self):
        assert self.settings.gitlab_project_id == 17
        assert self.settings.gitlab_token.get_secret_value() == "project-token"
        assert self.settings.target_branch == "main"
        assert self.settings.queue_label == "team-queue"
        assert self.settings.hotfix_label == "urgent"

    def and_shared_runtime_values_are_exposed(self):
        assert self.settings.poll_interval_seconds == 12
