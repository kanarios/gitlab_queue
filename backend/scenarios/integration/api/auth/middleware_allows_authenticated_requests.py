"""Test that middleware allows authenticated requests to protected routes."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.fakes import FakeHistoryRepo, FakeUnitOfWork
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "auth middleware allows authenticated requests to protected routes"

    def given_app_with_valid_token(self):
        self.app, self.state = created_test_app()
        self.client = TestClient(self.app)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Use FakeUnitOfWork to avoid database calls
        uow = FakeUnitOfWork(history=FakeHistoryRepo())

        self.state.uow_factory = lambda db: uow

    def when_protected_route_is_accessed_with_token(self):
        self.response = self.client.get("/api/history", headers=self.headers)

    def then_it_should_not_return_401(self):
        # Should not be 401 - might be 200 or another error depending on data
        assert self.response.status_code != 401
