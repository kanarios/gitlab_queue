"""Test that /api/history/{iid} returns 404 for non-existent MR."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.fakes import FakeHistoryRepo, FakeUnitOfWork
from scenarios.schemas.status_code import NotFoundStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "try to get history item for non-existent mr"

    def given_app_with_empty_history(self):
        history_repo = FakeHistoryRepo(get_by_iid_result=None)
        uow = FakeUnitOfWork(history=history_repo)

        # Create app with uow_factory DI
        self.app, self.state = created_test_app()
        self.state.uow_factory = lambda db: uow
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_nonexistent_item_is_requested(self):
        self.response = self.client.get(
            "/api/history/99999",
            headers=self.headers,
        )

    def then_it_should_return_404(self):
        assert self.response.status_code == NotFoundStatusSchema
        data = self.response.json()
        assert "not found" in data["detail"].lower()
