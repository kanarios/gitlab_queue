"""Test that /api/config returns default project web url."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app, created_test_jwt
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "config endpoint returns default project web url"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_config_is_requested(self):
        self.response = self.client.get("/api/config", headers=self.headers)

    def then_it_should_return_default_project_web_url(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()
        assert data["project_web_url"] == "https://gitlab.com/test/project"
