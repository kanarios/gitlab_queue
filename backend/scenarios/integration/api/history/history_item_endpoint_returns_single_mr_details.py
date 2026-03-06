"""Test that /api/history/{iid} returns a single MR."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import (
    create_test_queue_item,
    created_test_app,
    created_test_jwt,
)
from scenarios.fakes import FakeHistoryRepo, FakeUnitOfWork
from scenarios.library import QueueState
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient

from ._helpers import _queue_item_to_history_model


class Scenario(vedro.Scenario):
    subject = "history item endpoint returns single MR details"

    def given_app_with_history_item(self):
        item = create_test_queue_item(
            mr_iid=42,
            title="Test MR #42",
            state=QueueState.MERGED,
        )
        history_repo = FakeHistoryRepo(
            get_by_iid_result=_queue_item_to_history_model(item),
        )
        uow = FakeUnitOfWork(history=history_repo)

        # Create app with uow_factory DI
        self.app, self.state = created_test_app()
        self.state.uow_factory = lambda db: uow
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_history_item_is_requested(self):
        self.response = self.client.get(
            "/api/history/42",
            headers=self.headers,
        )

    def then_it_should_return_item_details(self):
        assert self.response.status_code == OkStatusSchema
        data = self.response.json()
        assert data["mr_iid"] == 42
        assert data["title"] == "Test MR #42"
        assert data["status"] == "merged"
