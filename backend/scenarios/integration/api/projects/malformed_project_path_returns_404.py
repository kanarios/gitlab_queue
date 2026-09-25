"""Malformed project identifiers return 404 instead of a server error."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app, created_test_jwt
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "malformed project path returns 404"

    def given_authenticated_project_api(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)

    def when_history_is_requested_for_a_non_numeric_project(self):
        self.response = self.client.get(
            "/api/projects/not-a-project/history",
            headers={"Authorization": f"Bearer {self.token}"},
        )

    def then_api_returns_not_found_instead_of_internal_server_error(self):
        assert self.response.status_code == 404
        assert self.response.json()["detail"] == "Project not found"
