"""Project queue routes enforce explicit selection and JWT membership."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app
from starlette.testclient import TestClient

from gitlab_queue.auth.jwt_handler import create_access_token


class Scenario(vedro.Scenario):
    subject = "project queue route is isolated by configured project and membership"

    def given_two_projects_and_access_to_one(self):
        self.app, self.state = created_test_app()
        self.state.project_components = {101: None, 202: None}
        token = create_access_token(
            {"id": 1, "username": "member", "project_ids": [101]},
            self.state.settings,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.headers = {"Authorization": f"Bearer {token}"}

    def when_project_and_legacy_routes_are_requested(self):
        self.allowed = self.client.get("/api/projects/101/queue", headers=self.headers)
        self.denied = self.client.get("/api/projects/202/queue", headers=self.headers)
        self.legacy = self.client.get("/api/queue", headers=self.headers)

    def then_authorized_project_is_returned(self):
        assert self.allowed.status_code == 200

    def and_other_project_is_hidden(self):
        assert self.denied.status_code == 404

    def and_legacy_alias_requires_a_single_configured_project(self):
        assert self.legacy.status_code == 400
