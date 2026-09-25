"""Project entries inherit shared branch and queue label settings."""

from __future__ import annotations

import vedro

from gitlab_queue.config import Settings


class Scenario(vedro.Scenario):
    subject = "project entries inherit global branch and label defaults"

    def given_global_defaults_and_project_overrides(self):
        self.settings = Settings(
            jwt_secret="j" * 64,
            target_branch="develop",
            queue_label="global-queue",
            hotfix_label="global-hotfix",
            projects_json=(
                '[{"project_id":123,"token":"token-a"},'
                '{"project_id":456,"token":"token-b","target_branch":"main",'
                '"queue_label":"project-queue","hotfix_label":"project-hotfix"}]'
            ),
        )

    def when_project_configs_are_read(self):
        self.projects = self.settings.projects

    def then_unspecified_fields_inherit_global_defaults(self):
        assert self.projects[0].target_branch == "develop"
        assert self.projects[0].queue_label == "global-queue"
        assert self.projects[0].hotfix_label == "global-hotfix"

    def and_explicit_project_values_override_global_defaults(self):
        assert self.projects[1].target_branch == "main"
        assert self.projects[1].queue_label == "project-queue"
        assert self.projects[1].hotfix_label == "project-hotfix"
