"""Test that /api/history validates pagination parameters."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.schemas.status_code import UnprocessableEntityStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "history endpoint validates pagination parameters"

    def given_app(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_history_is_called_with_invalid_params(self):
        # page < 1 should fail validation
        self.response_invalid_page = self.client.get(
            "/api/history?page=0",
            headers=self.headers,
        )
        # per_page > 100 should fail validation
        self.response_invalid_per_page = self.client.get(
            "/api/history?per_page=101",
            headers=self.headers,
        )

    def then_invalid_page_should_return_422(self):
        assert self.response_invalid_page.status_code == UnprocessableEntityStatusSchema

    def and_invalid_per_page_should_return_422(self):
        assert self.response_invalid_per_page.status_code == UnprocessableEntityStatusSchema
