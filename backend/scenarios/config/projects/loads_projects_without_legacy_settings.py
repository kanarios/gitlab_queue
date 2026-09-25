"""A project list can be the only source of GitLab project credentials."""

import vedro

from gitlab_queue.config import load_settings


class Scenario(vedro.Scenario):
    subject = "load project list without legacy GitLab settings"

    def given_projects_environment(self):
        self.env_vars = {
            "GITLAB_QUEUE_PROJECTS": (
                '[{"project_id": 17, "token": "glpat-one", "target_branch": "main", '
                '"queue_label": "queue-one", "hotfix_label": "urgent-one"}, '
                '{"project_id": 29, "token": "glpat-two"}]'
            ),
            "GITLAB_QUEUE_JWT_SECRET": "j" * 64,
            "GITLAB_QUEUE_WEBHOOK_SECRET": "webhook-secret",
        }

    def when_settings_are_loaded(self):
        self.settings = load_settings(self.env_vars)

    def then_both_project_configs_are_loaded(self):
        assert [project.project_id for project in self.settings.projects] == [17, 29]

    def and_project_specific_options_are_preserved(self):
        project = self.settings.projects[0]
        assert project.token.get_secret_value() == "glpat-one"
        assert project.target_branch == "main"
        assert project.queue_label == "queue-one"
        assert project.hotfix_label == "urgent-one"
