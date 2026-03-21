"""Test that parse_merge_request extracts project_id from GitLab API response."""

from __future__ import annotations

import vedro

from gitlab_queue.models.retorts import parse_merge_request


class Scenario(vedro.Scenario):
    subject = "parse_merge_request extracts project_id from API response"

    def given_api_response_with_project_id(self):
        self.api_data = {
            "iid": 42,
            "title": "Test MR",
            "state": "opened",
            "labels": [],
            "sha": "abc123",
            "source_branch": "feature",
            "target_branch": "master",
            "merge_status": "can_be_merged",
            "author": {"id": 1, "name": "User", "username": "user"},
            "project_id": 12345,
        }

    def when_merge_request_is_parsed(self):
        self.result = parse_merge_request(self.api_data)

    def then_project_id_is_extracted(self):
        assert self.result.project_id == 12345
