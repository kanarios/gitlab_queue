"""API history endpoint tests for Vedro scenarios.

Tests the /api/history endpoints for paginated history retrieval and filtering.

Example:
    >>> vedro run scenarios/integration/api_history.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.contexts.api_helpers import (
    create_test_app,
    create_test_history_items,
    create_test_jwt,
    create_test_queue_item,
)
from starlette.testclient import TestClient

from gitlab_queue.models.queue_item import QueueItem


def _queue_item_to_history_model(item: QueueItem) -> MagicMock:
    """Convert QueueItem to mock MergeRequestHistoryModel.

    ModelConverter.history_model_to_queue_item expects:
    - queued_at, started_at, finished_at as ISO format strings
    - labels as JSON string
    """
    model = MagicMock()
    model.iid = item.mr_iid
    model.title = item.title
    model.author_name = item.author_name
    model.author_username = item.author_username
    model.author_avatar = item.author_avatar
    model.status = item.state
    model.is_hotfix = item.is_hotfix
    model.labels = json.dumps(item.labels) if item.labels else "[]"
    model.target_branch = item.target_branch
    # Convert datetime objects to ISO format strings
    model.queued_at = item.queued_at.isoformat() if item.queued_at else None
    model.started_at = item.started_at.isoformat() if item.started_at else None
    finished = item.finished_at or datetime.now(UTC)
    model.finished_at = finished.isoformat()
    model.pipeline_id = item.pipeline_id
    model.pipeline_status = item.pipeline_status
    model.failure_reason = item.last_error
    return model


# Note: Starlette's BaseHTTPMiddleware has known issues with async context
# handling when combined with TestClient. Using raise_server_exceptions=False
# to work around this issue for authenticated endpoints.


# =============================================================================
# History List Tests
# =============================================================================


class Scenario__get_history_returns_paginated_results(vedro.Scenario):
    """Test that /api/history returns paginated results."""

    subject = "history endpoint returns paginated results"

    def given_app_with_history_data(self):
        # Mock history repository
        history_items = create_test_history_items(count=15)
        mock_result = MagicMock()
        mock_result.items = [_queue_item_to_history_model(item) for item in history_items[:10]]
        mock_result.page = 1
        mock_result.per_page = 10
        mock_result.total = 15
        mock_result.total_pages = 2

        # Create a mock UnitOfWork context manager
        mock_uow = AsyncMock()
        mock_uow.history = MagicMock()
        mock_uow.history.get_history = AsyncMock(return_value=mock_result)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        # Patch UnitOfWork BEFORE creating the app
        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

        # Create app and client AFTER patching
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_history_endpoint_is_called(self):
        self.response = self.client.get(
            "/api/history?page=1&per_page=10",
            headers=self.headers,
        )

    def then_it_should_return_paginated_data(self):
        # Debug: print response if not 200
        if self.response.status_code != 200:
            print(f"DEBUG: Status={self.response.status_code}, Body={self.response.text[:500]}")
        assert self.response.status_code == 200
        data = self.response.json()

        assert "items" in data
        assert "pagination" in data
        assert len(data["items"]) <= 10

        pagination = data["pagination"]
        assert pagination["page"] == 1
        assert pagination["per_page"] == 10
        assert pagination["total"] == 15
        assert pagination["total_pages"] == 2

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow


class Scenario__get_history_validates_page_params(vedro.Scenario):
    """Test that /api/history validates pagination parameters."""

    subject = "history endpoint validates pagination parameters"

    def given_app(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
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
        assert self.response_invalid_page.status_code == 422

    def then_invalid_per_page_should_return_422(self):
        assert self.response_invalid_per_page.status_code == 422


class Scenario__get_history_filters_by_status(vedro.Scenario):
    """Test that /api/history filters by status."""

    subject = "history endpoint filters by status parameter"

    def given_app_with_mock_history(self):
        # Create mock history with specific status
        merged_item = create_test_queue_item(mr_iid=100, state="merged")
        mock_result = MagicMock()
        mock_result.items = [_queue_item_to_history_model(merged_item)]
        mock_result.page = 1
        mock_result.per_page = 20
        mock_result.total = 1
        mock_result.total_pages = 1

        mock_uow = AsyncMock()
        mock_uow.history = MagicMock()
        mock_uow.history.get_history = AsyncMock(return_value=mock_result)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)
        self._mock_uow = mock_uow

        # Create app AFTER patching
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_history_is_called_with_status_filter(self):
        self.response = self.client.get(
            "/api/history?status=merged",
            headers=self.headers,
        )

    def then_it_should_pass_status_to_repository(self):
        assert self.response.status_code == 200
        # Verify the status filter was passed to get_history
        call_args = self._mock_uow.history.get_history.call_args
        assert call_args is not None
        assert call_args.kwargs.get("status_filter") == "merged"

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow


class Scenario__get_history_filters_by_date_range(vedro.Scenario):
    """Test that /api/history filters by date range."""

    subject = "history endpoint filters by date range"

    def given_app_with_mock_history(self):
        mock_result = MagicMock()
        mock_result.items = []
        mock_result.page = 1
        mock_result.per_page = 20
        mock_result.total = 0
        mock_result.total_pages = 0

        mock_uow = AsyncMock()
        mock_uow.history = MagicMock()
        mock_uow.history.get_history = AsyncMock(return_value=mock_result)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)
        self._mock_uow = mock_uow

        # Create app AFTER patching
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_history_is_called_with_date_filter(self):
        today = datetime.now(UTC).date()
        yesterday = today - timedelta(days=1)

        self.response = self.client.get(
            f"/api/history?date_from={yesterday}&date_to={today}",
            headers=self.headers,
        )

    def then_it_should_pass_dates_to_repository(self):
        assert self.response.status_code == 200
        call_args = self._mock_uow.history.get_history.call_args
        assert call_args is not None
        assert call_args.kwargs.get("date_from") is not None
        assert call_args.kwargs.get("date_to") is not None

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow


class Scenario__get_history_searches_by_title(vedro.Scenario):
    """Test that /api/history searches by title."""

    subject = "history endpoint searches by title"

    def given_app_with_searchable_history(self):
        # Create items with specific titles
        item1 = create_test_queue_item(mr_iid=100, title="Fix login bug")
        item2 = create_test_queue_item(mr_iid=101, title="Add new feature")

        mock_result = MagicMock()
        mock_result.items = [
            _queue_item_to_history_model(item1),
            _queue_item_to_history_model(item2),
        ]
        mock_result.page = 1
        mock_result.per_page = 20
        mock_result.total = 2
        mock_result.total_pages = 1

        mock_uow = AsyncMock()
        mock_uow.history = MagicMock()
        mock_uow.history.get_history = AsyncMock(return_value=mock_result)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

        # Create app AFTER patching
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_history_is_searched(self):
        self.response = self.client.get(
            "/api/history?search=login",
            headers=self.headers,
        )

    def then_it_should_filter_results(self):
        assert self.response.status_code == 200
        data = self.response.json()
        # Search filter is applied in-memory, so check results
        for item in data["items"]:
            # Either title, author_name, or author_username should contain search term
            title_match = "login" in item.get("title", "").lower()
            author_name_match = "login" in item.get("author", {}).get("name", "").lower()
            author_username_match = "login" in item.get("author", {}).get("username", "").lower()
            iid_match = str(item.get("mr_iid", "")) == "login"
            assert title_match or author_name_match or author_username_match or iid_match

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow


class Scenario__get_history_requires_authentication(vedro.Scenario):
    """Test that /api/history requires authentication."""

    subject = "history endpoint requires authentication"

    def given_app(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_history_is_called_without_token(self):
        self.response = self.client.get("/api/history")

    def then_it_should_return_401(self):
        assert self.response.status_code == 401


# =============================================================================
# History Item Tests
# =============================================================================


class Scenario__get_history_item_returns_single_mr(vedro.Scenario):
    """Test that /api/history/{iid} returns a single MR."""

    subject = "history item endpoint returns single MR details"

    def given_app_with_history_item(self):
        # Create mock item
        item = create_test_queue_item(
            mr_iid=42,
            title="Test MR #42",
            state="merged",
        )
        mock_model = _queue_item_to_history_model(item)

        mock_uow = AsyncMock()
        mock_uow.history = MagicMock()
        mock_uow.history.get_by_iid = AsyncMock(return_value=mock_model)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

        # Create app AFTER patching
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_history_item_is_requested(self):
        self.response = self.client.get(
            "/api/history/42",
            headers=self.headers,
        )

    def then_it_should_return_item_details(self):
        assert self.response.status_code == 200
        data = self.response.json()
        assert data["mr_iid"] == 42
        assert data["title"] == "Test MR #42"
        assert data["status"] == "merged"

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow


class Scenario__get_history_item_returns_404_for_missing(vedro.Scenario):
    """Test that /api/history/{iid} returns 404 for non-existent MR."""

    subject = "history item endpoint returns 404 for non-existent MR"

    def given_app_with_empty_history(self):
        mock_uow = AsyncMock()
        mock_uow.history = MagicMock()
        mock_uow.history.get_by_iid = AsyncMock(return_value=None)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

        # Create app AFTER patching
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_nonexistent_item_is_requested(self):
        self.response = self.client.get(
            "/api/history/99999",
            headers=self.headers,
        )

    def then_it_should_return_404(self):
        assert self.response.status_code == 404
        data = self.response.json()
        assert "not found" in data["detail"].lower()

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
