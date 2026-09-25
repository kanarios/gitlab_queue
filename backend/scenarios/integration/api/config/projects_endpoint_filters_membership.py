"""The projects endpoint exposes only projects authorized by the JWT."""

from __future__ import annotations

from types import SimpleNamespace

import vedro
from scenarios.contexts.api_helpers import created_test_app
from starlette.testclient import TestClient

from gitlab_queue.auth.jwt_handler import create_access_token


class Scenario(vedro.Scenario):
    subject = "projects endpoint filters configured projects by membership"

    def given_two_projects_and_membership_in_one(self):
        self.app, self.state = created_test_app()
        component = SimpleNamespace(gitlab_client=self.state.gitlab_client)
        self.state.project_components = {101: component, 202: component}
        token = create_access_token(
            {"id": 1, "username": "member", "project_ids": [202]},
            self.state.settings,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.headers = {"Authorization": f"Bearer {token}"}

    def when_projects_are_requested(self):
        self.response = self.client.get("/api/projects", headers=self.headers)

    def then_only_authorized_project_is_returned(self):
        assert self.response.status_code == 200
        projects = self.response.json()["projects"]
        assert [project["project_id"] for project in projects] == [202]
        assert projects[0]["name"] == "test/project"
