"""Repositories keep queue, history, and analytics data within one project."""

from __future__ import annotations

from datetime import UTC, date, datetime

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import (
    create_tables,
    create_test_history_model,
    create_test_hourly_model,
    create_test_mr_model,
)

from gitlab_queue.db.repositories import AnalyticsRepository, HistoryRepository, MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "repositories isolate identical merge request ids and analytics by project"

    async def given_two_projects_have_same_iid_and_different_data(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)
        now = datetime.now(UTC)
        timestamp = now.replace(minute=0, second=0, microsecond=0).isoformat()
        today = date.today()

        first_mr = create_test_mr_model(iid=42, title="First project MR")
        first_mr.project_id = 101
        second_mr = create_test_mr_model(iid=42, title="Second project MR")
        second_mr.project_id = 202

        first_history = create_test_history_model(
            iid=42,
            status="merged",
            finished_at=now.isoformat(),
            queued_at=now.isoformat(),
        )
        first_history.project_id = 101
        second_history = create_test_history_model(
            iid=42,
            status="failed",
            finished_at=now.isoformat(),
            queued_at=now.isoformat(),
        )
        second_history.project_id = 202

        first_hourly = create_test_hourly_model(timestamp=timestamp, queue_depth=3)
        first_hourly.project_id = 101
        second_hourly = create_test_hourly_model(timestamp=timestamp, queue_depth=30)
        second_hourly.project_id = 202

        async with self.db.transaction() as session:
            session.add_all([first_mr, second_mr, first_history, second_history, first_hourly, second_hourly])
            await session.flush()

        self.today = today

    async def when_each_project_is_queried(self):
        async with self.db.session() as session:
            first_mrs = MergeRequestRepository(session, project_id=101)
            second_mrs = MergeRequestRepository(session, project_id=202)
            first_mr = await first_mrs.get_by_iid(42)
            second_mr = await second_mrs.get_by_iid(42)
            self.first_mr = (first_mr.project_id, first_mr.title) if first_mr else None
            self.second_mr = (second_mr.project_id, second_mr.title) if second_mr else None
            self.first_queue_count = await first_mrs.count_active()
            self.second_queue_count = await second_mrs.count_active()

            first_history = HistoryRepository(session, project_id=101)
            second_history = HistoryRepository(session, project_id=202)
            first_history_row = await first_history.get_by_iid(42)
            second_history_row = await second_history.get_by_iid(42)
            self.first_history = first_history_row.status if first_history_row else None
            self.second_history = second_history_row.status if second_history_row else None
            self.first_history_page = await first_history.get_history()
            self.second_history_page = await second_history.get_history()

            first_analytics = AnalyticsRepository(session, project_id=101)
            second_analytics = AnalyticsRepository(session, project_id=202)
            self.first_metrics = await first_analytics.get_metrics()
            self.second_metrics = await second_analytics.get_metrics()
            first_daily = await first_analytics.aggregate_daily(self.today)
            second_daily = await second_analytics.aggregate_daily(self.today)
            self.first_daily = (
                (
                    first_daily.project_id,
                    first_daily.total_processed,
                    first_daily.success_count,
                )
                if first_daily
                else None
            )
            self.second_daily = (
                (
                    second_daily.project_id,
                    second_daily.total_processed,
                    second_daily.failed_count,
                )
                if second_daily
                else None
            )

    def then_each_identity_lookup_returns_its_project_record(self):
        assert self.first_mr == (101, "First project MR")
        assert self.second_mr == (202, "Second project MR")
        assert self.first_history == "merged"
        assert self.second_history == "failed"

    def and_project_queue_and_history_totals_are_separate(self):
        assert self.first_queue_count == self.second_queue_count == 1
        assert self.first_history_page.total == self.second_history_page.total == 1

    def and_dashboard_analytics_are_separate(self):
        assert self.first_metrics.total_in_queue == self.second_metrics.total_in_queue == 1
        assert self.first_metrics.merged_count == 1
        assert self.first_metrics.failed_count == 0
        assert self.second_metrics.merged_count == 0
        assert self.second_metrics.failed_count == 1
        assert self.first_metrics.hourly_trend[0]["queue_depth"] == 3
        assert self.second_metrics.hourly_trend[0]["queue_depth"] == 30

    def and_daily_aggregation_uses_only_matching_project_data(self):
        assert self.first_daily == (101, 1, 1)
        assert self.second_daily == (202, 1, 1)

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
