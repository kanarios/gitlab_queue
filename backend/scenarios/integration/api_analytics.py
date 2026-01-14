"""API analytics endpoint tests for Vedro scenarios.

Tests the /api/analytics endpoints for summary metrics, hourly data, and outcomes.

Example:
    >>> vedro run scenarios/integration/api_analytics.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.contexts.api_helpers import (
    create_test_app,
    create_test_jwt,
)
from starlette.testclient import TestClient

# Note: Starlette's BaseHTTPMiddleware has known issues with async context
# handling when combined with TestClient. Using raise_server_exceptions=False
# to work around this issue for authenticated endpoints.


# =============================================================================
# Analytics Summary Tests
# =============================================================================


class Scenario__get_summary_returns_metrics(vedro.Scenario):
    """Test that /api/analytics/summary returns metrics."""

    subject = "analytics summary endpoint returns aggregate metrics"

    def given_app_with_analytics_data(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Mock stats
        mock_stats = MagicMock()
        mock_stats.total_processed = 100
        mock_stats.success_count = 90
        mock_stats.failed_count = 5
        mock_stats.conflict_count = 3
        mock_stats.timeout_count = 2
        mock_stats.avg_wait_time_seconds = 300
        mock_stats.avg_processing_time_seconds = 600

        mock_uow = AsyncMock()
        mock_uow.history = AsyncMock()
        mock_uow.history.get_stats_for_period = AsyncMock(return_value=mock_stats)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

    def when_summary_endpoint_is_called(self):
        self.response = self.client.get(
            "/api/analytics/summary",
            headers=self.headers,
        )

    def then_it_should_return_metrics(self):
        assert self.response.status_code == 200
        data = self.response.json()

        assert "total_processed" in data
        assert "avg_wait_time_seconds" in data
        assert "avg_processing_time_seconds" in data
        assert "success_rate_percent" in data
        assert "daily_throughput" in data
        assert "period_days" in data

        assert data["total_processed"] == 100
        assert data["success_rate_percent"] == 90.0
        assert data["period_days"] == 7  # default

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow


class Scenario__get_summary_respects_days_param(vedro.Scenario):
    """Test that /api/analytics/summary respects days parameter."""

    subject = "analytics summary endpoint respects days parameter"

    def given_app(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        mock_stats = MagicMock()
        mock_stats.total_processed = 50
        mock_stats.success_count = 45
        mock_stats.avg_wait_time_seconds = 200
        mock_stats.avg_processing_time_seconds = 400

        mock_uow = AsyncMock()
        mock_uow.history = AsyncMock()
        mock_uow.history.get_stats_for_period = AsyncMock(return_value=mock_stats)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)
        self._mock_uow = mock_uow

    def when_summary_is_called_with_days(self):
        self.response = self.client.get(
            "/api/analytics/summary?days=30",
            headers=self.headers,
        )

    def then_it_should_use_custom_days(self):
        assert self.response.status_code == 200
        data = self.response.json()
        assert data["period_days"] == 30

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow


class Scenario__analytics_validates_days_bounds(vedro.Scenario):
    """Test that /api/analytics validates days parameter bounds."""

    subject = "analytics endpoints validate days parameter bounds"

    def given_app(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_summary_is_called_with_invalid_days(self):
        # days < 1 should fail
        self.response_too_low = self.client.get(
            "/api/analytics/summary?days=0",
            headers=self.headers,
        )
        # days > 365 should fail
        self.response_too_high = self.client.get(
            "/api/analytics/summary?days=366",
            headers=self.headers,
        )

    def then_invalid_days_should_return_422(self):
        assert self.response_too_low.status_code == 422
        assert self.response_too_high.status_code == 422


class Scenario__analytics_requires_authentication(vedro.Scenario):
    """Test that /api/analytics requires authentication."""

    subject = "analytics endpoints require authentication"

    def given_app(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def when_analytics_is_called_without_token(self):
        self.summary_response = self.client.get("/api/analytics/summary")
        self.hourly_response = self.client.get("/api/analytics/hourly")
        self.outcomes_response = self.client.get("/api/analytics/outcomes")

    def then_summary_should_return_401(self):
        assert self.summary_response.status_code == 401

    def then_hourly_should_return_401(self):
        assert self.hourly_response.status_code == 401

    def then_outcomes_should_return_401(self):
        assert self.outcomes_response.status_code == 401


# =============================================================================
# Hourly Analytics Tests
# =============================================================================


class Scenario__get_hourly_returns_data_points(vedro.Scenario):
    """Test that /api/analytics/hourly returns hourly data points."""

    subject = "analytics hourly endpoint returns data points"

    def given_app_with_hourly_data(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Mock hourly data
        now = datetime.now(UTC)
        hourly_data = [
            {"timestamp": (now).isoformat(), "queue_depth": 5, "processed_count": 3},
            {"timestamp": (now).isoformat(), "queue_depth": 4, "processed_count": 2},
        ]

        mock_metrics = MagicMock()
        mock_metrics.hourly_trend = hourly_data

        mock_uow = AsyncMock()
        mock_uow.analytics = AsyncMock()
        mock_uow.analytics.get_metrics = AsyncMock(return_value=mock_metrics)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

    def when_hourly_endpoint_is_called(self):
        self.response = self.client.get(
            "/api/analytics/hourly",
            headers=self.headers,
        )

    def then_it_should_return_data_points(self):
        assert self.response.status_code == 200
        data = self.response.json()

        assert "data" in data
        assert "hours" in data
        assert data["hours"] == 24  # default

        # Verify data point structure
        if len(data["data"]) > 0:
            point = data["data"][0]
            assert "timestamp" in point
            assert "queue_depth" in point
            assert "processed_count" in point

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow


class Scenario__get_hourly_respects_hours_param(vedro.Scenario):
    """Test that /api/analytics/hourly respects hours parameter."""

    subject = "analytics hourly endpoint respects hours parameter"

    def given_app(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        mock_metrics = MagicMock()
        mock_metrics.hourly_trend = []

        mock_uow = AsyncMock()
        mock_uow.analytics = AsyncMock()
        mock_uow.analytics.get_metrics = AsyncMock(return_value=mock_metrics)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

    def when_hourly_is_called_with_hours(self):
        self.response = self.client.get(
            "/api/analytics/hourly?hours=48",
            headers=self.headers,
        )

    def then_it_should_return_custom_hours(self):
        assert self.response.status_code == 200
        data = self.response.json()
        assert data["hours"] == 48

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow


class Scenario__hourly_validates_hours_bounds(vedro.Scenario):
    """Test that /api/analytics/hourly validates hours parameter bounds."""

    subject = "analytics hourly endpoint validates hours parameter bounds"

    def given_app(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def when_hourly_is_called_with_invalid_hours(self):
        # hours < 1 should fail
        self.response_too_low = self.client.get(
            "/api/analytics/hourly?hours=0",
            headers=self.headers,
        )
        # hours > 168 (7 days) should fail
        self.response_too_high = self.client.get(
            "/api/analytics/hourly?hours=169",
            headers=self.headers,
        )

    def then_invalid_hours_should_return_422(self):
        assert self.response_too_low.status_code == 422
        assert self.response_too_high.status_code == 422


# =============================================================================
# Outcomes Analytics Tests
# =============================================================================


class Scenario__get_outcomes_returns_breakdown(vedro.Scenario):
    """Test that /api/analytics/outcomes returns outcome breakdown."""

    subject = "analytics outcomes endpoint returns outcome breakdown"

    def given_app_with_outcomes_data(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        mock_stats = MagicMock()
        mock_stats.total_processed = 100
        mock_stats.success_count = 80
        mock_stats.failed_count = 10
        mock_stats.conflict_count = 7
        mock_stats.timeout_count = 3

        mock_uow = AsyncMock()
        mock_uow.history = AsyncMock()
        mock_uow.history.get_stats_for_period = AsyncMock(return_value=mock_stats)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

    def when_outcomes_endpoint_is_called(self):
        self.response = self.client.get(
            "/api/analytics/outcomes",
            headers=self.headers,
        )

    def then_it_should_return_breakdown(self):
        assert self.response.status_code == 200
        data = self.response.json()

        assert "outcomes" in data
        assert "total" in data
        assert "period_days" in data

        # Verify outcome structure
        outcomes = data["outcomes"]
        assert len(outcomes) > 0

        for outcome in outcomes:
            assert "name" in outcome
            assert "count" in outcome
            assert "percentage" in outcome

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow


# =============================================================================
# Failure Reasons Analytics Tests
# =============================================================================


class Scenario__get_failure_reasons_returns_list(vedro.Scenario):
    """Test that /api/analytics/failure-reasons returns failure reasons."""

    subject = "analytics failure-reasons endpoint returns failure reason breakdown"

    def given_app_with_failure_data(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Create mock history items with failures
        failed_item1 = MagicMock()
        failed_item1.status = "failed"
        failed_item1.failure_reason = "Pipeline failed: test failure"

        failed_item2 = MagicMock()
        failed_item2.status = "conflict"
        failed_item2.failure_reason = "Merge conflict in src/main.py"

        merged_item = MagicMock()
        merged_item.status = "merged"
        merged_item.failure_reason = None

        mock_result = MagicMock()
        mock_result.items = [failed_item1, failed_item2, merged_item]
        mock_result.page = 1
        mock_result.per_page = 1000
        mock_result.total = 3
        mock_result.total_pages = 1

        mock_uow = AsyncMock()
        mock_uow.history = AsyncMock()
        mock_uow.history.get_history = AsyncMock(return_value=mock_result)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

    def when_failure_reasons_endpoint_is_called(self):
        self.response = self.client.get(
            "/api/analytics/failure-reasons",
            headers=self.headers,
        )

    def then_it_should_return_reasons(self):
        assert self.response.status_code == 200
        data = self.response.json()

        assert "reasons" in data
        assert "total_failures" in data
        assert "period_days" in data

        # Should have 2 failures
        assert data["total_failures"] == 2

        # Verify reason structure
        for reason in data["reasons"]:
            assert "reason" in reason
            assert "count" in reason
            assert "percentage" in reason

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow


class Scenario__get_failure_reasons_handles_no_failures(vedro.Scenario):
    """Test that /api/analytics/failure-reasons handles no failures gracefully."""

    subject = "analytics failure-reasons endpoint handles no failures gracefully"

    def given_app_with_no_failures(self):
        self.app, self.state = create_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = create_test_jwt(self.state.settings)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # All items are merged (no failures)
        merged_item = MagicMock()
        merged_item.status = "merged"
        merged_item.failure_reason = None

        mock_result = MagicMock()
        mock_result.items = [merged_item]
        mock_result.page = 1
        mock_result.per_page = 1000
        mock_result.total = 1
        mock_result.total_pages = 1

        mock_uow = AsyncMock()
        mock_uow.history = AsyncMock()
        mock_uow.history.get_history = AsyncMock(return_value=mock_result)
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        import gitlab_queue.api.routes as routes_module

        self._original_uow = routes_module.UnitOfWork
        routes_module.UnitOfWork = MagicMock(return_value=mock_uow)

    def when_failure_reasons_endpoint_is_called(self):
        self.response = self.client.get(
            "/api/analytics/failure-reasons",
            headers=self.headers,
        )

    def then_it_should_return_empty_reasons(self):
        assert self.response.status_code == 200
        data = self.response.json()

        assert "reasons" in data
        assert "total_failures" in data
        assert data["total_failures"] == 0
        assert len(data["reasons"]) == 0

    def cleanup(self):
        import gitlab_queue.api.routes as routes_module

        routes_module.UnitOfWork = self._original_uow
