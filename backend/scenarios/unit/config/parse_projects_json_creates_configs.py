"""Test that _parse_projects_json creates ProjectConfig list from valid JSON."""

from __future__ import annotations

import vedro

from gitlab_queue.config import ProjectConfig, _parse_projects_json


class Scenario(vedro.Scenario):
    subject = "parse projects JSON creates configs from valid input"

    def given_valid_projects_json(self):
        self.raw = '[{"project_id": 123, "token": "glpat-aaa"}, {"project_id": 456, "token": "glpat-bbb", "target_branch": "main"}]'

    def when_json_is_parsed(self):
        self.result = _parse_projects_json(self.raw)

    def then_two_configs_are_created(self):
        assert len(self.result) == 2

    def and_first_config_has_correct_project_id(self):
        assert self.result[0].project_id == 123

    def and_first_config_has_correct_token(self):
        assert self.result[0].token.get_secret_value() == "glpat-aaa"

    def and_first_config_uses_default_target_branch(self):
        assert self.result[0].target_branch == "master"

    def and_second_config_has_custom_target_branch(self):
        assert self.result[1].target_branch == "main"

    def and_configs_are_frozen_dataclasses(self):
        assert isinstance(self.result[0], ProjectConfig)
        assert isinstance(self.result[1], ProjectConfig)
