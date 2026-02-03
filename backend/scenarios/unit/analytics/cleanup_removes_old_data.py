"""Test that cleanup removes data older than retention period.

Covers _cleanup_hourly_analytics (lines 205-238):
- Calls analytics.cleanup_hourly(retention_days)
- Runs VACUUM when records are deleted
- No VACUUM when nothing to clean up

Also covers _cleanup_history for 1-year retention.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.jobs.analytics import AnalyticsJobProcessor


class Scenario(vedro.Scenario):
    subject = "cleanup removes hourly analytics older than 30 days and runs vacuum"

    def given_analytics_processor_with_old_data(self):
        self.database = MagicMock()
        self.settings = MagicMock()

        self.mock_uow = MagicMock()
        self.mock_uow.__aenter__ = AsyncMock(return_value=self.mock_uow)
        self.mock_uow.__aexit__ = AsyncMock(return_value=None)

        self.mock_uow.analytics = MagicMock()
        self.mock_uow.analytics.cleanup_hourly = AsyncMock(return_value=150)

        self.processor = AnalyticsJobProcessor(
            database=self.database,
            settings=self.settings,
        )
        self.processor._vacuum_database = AsyncMock()

    async def when_cleanup_hourly_analytics_is_called(self):
        with patch(
            "gitlab_queue.jobs.analytics.UnitOfWork",
            return_value=self.mock_uow,
        ):
            await self.processor._cleanup_hourly_analytics()

    def then_cleanup_was_called_with_30_day_retention(self):
        self.mock_uow.analytics.cleanup_hourly.assert_called_once_with(30)

    def and_vacuum_was_triggered(self):
        self.processor._vacuum_database.assert_called_once()


class Scenario2(vedro.Scenario):
    subject = "cleanup skips vacuum when no records are deleted"

    def given_analytics_processor_with_no_old_data(self):
        self.database = MagicMock()
        self.settings = MagicMock()

        self.mock_uow = MagicMock()
        self.mock_uow.__aenter__ = AsyncMock(return_value=self.mock_uow)
        self.mock_uow.__aexit__ = AsyncMock(return_value=None)

        self.mock_uow.analytics = MagicMock()
        self.mock_uow.analytics.cleanup_hourly = AsyncMock(return_value=0)

        self.processor = AnalyticsJobProcessor(
            database=self.database,
            settings=self.settings,
        )
        self.processor._vacuum_database = AsyncMock()

    async def when_cleanup_hourly_analytics_is_called(self):
        with patch(
            "gitlab_queue.jobs.analytics.UnitOfWork",
            return_value=self.mock_uow,
        ):
            await self.processor._cleanup_hourly_analytics()

    def then_cleanup_was_called(self):
        self.mock_uow.analytics.cleanup_hourly.assert_called_once_with(30)

    def and_vacuum_was_not_triggered(self):
        self.processor._vacuum_database.assert_not_called()


class Scenario3(vedro.Scenario):
    subject = "history cleanup removes records older than 365 days"

    def given_analytics_processor_with_old_history(self):
        self.database = MagicMock()
        self.settings = MagicMock()

        self.mock_uow = MagicMock()
        self.mock_uow.__aenter__ = AsyncMock(return_value=self.mock_uow)
        self.mock_uow.__aexit__ = AsyncMock(return_value=None)

        self.mock_uow.history = MagicMock()
        self.mock_uow.history.cleanup_old_records = AsyncMock(return_value=50)

        self.processor = AnalyticsJobProcessor(
            database=self.database,
            settings=self.settings,
        )
        self.processor._vacuum_database = AsyncMock()

    async def when_cleanup_history_is_called(self):
        with patch(
            "gitlab_queue.jobs.analytics.UnitOfWork",
            return_value=self.mock_uow,
        ):
            await self.processor._cleanup_history()

    def then_cleanup_was_called_with_365_day_retention(self):
        self.mock_uow.history.cleanup_old_records.assert_called_once_with(365)

    def and_vacuum_was_triggered(self):
        self.processor._vacuum_database.assert_called_once()
