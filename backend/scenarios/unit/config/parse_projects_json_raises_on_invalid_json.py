"""Test that _parse_projects_json raises on invalid JSON input."""

from __future__ import annotations

import vedro

from gitlab_queue.config import _parse_projects_json


class Scenario(vedro.Scenario):
    subject = "parse projects JSON raises on invalid JSON"

    def given_malformed_json(self):
        self.raw = "not valid json {{"

    def when_json_is_parsed(self):
        try:
            _parse_projects_json(self.raw)
            self.error = None
        except ValueError as e:
            self.error = e

    def then_value_error_is_raised(self):
        assert self.error is not None

    def and_error_mentions_json(self):
        assert "not valid JSON" in str(self.error)
