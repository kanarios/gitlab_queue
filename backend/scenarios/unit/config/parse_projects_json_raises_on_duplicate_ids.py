"""Test that _parse_projects_json raises on duplicate project_ids."""

from __future__ import annotations

import vedro

from gitlab_queue.config import _parse_projects_json


class Scenario(vedro.Scenario):
    subject = "parse projects JSON raises on duplicate project IDs"

    def given_json_with_duplicate_project_ids(self):
        self.raw = '[{"project_id": 123, "token": "aaa"}, {"project_id": 123, "token": "bbb"}]'

    def when_json_is_parsed(self):
        try:
            _parse_projects_json(self.raw)
            self.error = None
        except ValueError as e:
            self.error = e

    def then_value_error_is_raised(self):
        assert self.error is not None

    def and_error_mentions_duplicate(self):
        assert "Duplicate project_id: 123" in str(self.error)
