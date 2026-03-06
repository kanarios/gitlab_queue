"""Test that /api/history filters by date range."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.api_helpers import (
    created_test_app,
    created_test_jwt,
)
from scenarios.fakes import FakeHistoryRepo, FakeUnitOfWork
from scenarios.schemas.status_code import OkStatusSchema
from starlette.testclient import TestClient


class Scenario(vedro.Scenario):
    subject = "history endpoint filters by date range"

    def given_app_with_mock_history(self):
        self._history_repo = FakeHistoryRepo()
        uow = FakeUnitOfWork(history=self._history_repo)

        # Create app with uow_factory DI
        self.app, self.state = created_test_app()
        self.state.uow_factory = lambda db: uow
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = created_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_history_is_called_with_date_filter(self):
        today = datetime.now(UTC).date()
        yesterday = today - timedelta(days=1)

        self.response = self.client.get(
            f"/api/history?date_from={yesterday}&date_to={today}",
            headers=self.headers,
        )

    def then_it_should_pass_dates_to_repository(self):
        assert self.response.status_code == OkStatusSchema
        assert len(self._history_repo.get_history_calls) == 1
        call_kwargs = self._history_repo.get_history_calls[0]
        assert call_kwargs.get("date_from") is not None
        assert call_kwargs.get("date_to") is not None
