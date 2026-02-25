"""Test that UnitOfWork provides all repository properties."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables

from gitlab_queue.db.repositories import (
    AnalyticsRepository,
    HistoryRepository,
    MergeRequestRepository,
    UnitOfWork,
)


class Scenario(vedro.Scenario):
    subject = "unit of work provides all repositories"

    async def given_initialized_database(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_unit_of_work_is_created(self):
        async with UnitOfWork(self.db) as uow:
            self.mr_repo = uow.merge_requests
            self.history_repo = uow.history
            self.analytics_repo = uow.analytics

    def then_merge_requests_should_be_available(self):
        assert isinstance(self.mr_repo, MergeRequestRepository)

    def and_history_should_be_available(self):
        assert isinstance(self.history_repo, HistoryRepository)

    def and_analytics_should_be_available(self):
        assert isinstance(self.analytics_repo, AnalyticsRepository)

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
