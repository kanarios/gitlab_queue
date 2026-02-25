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
        """
        Initialize a test database context, enter it, and create the required tables for tests.
        
        Sets self._db_ctx to the test database context manager and self.db to the entered database connection, then creates the database schema by calling the table-creation routine.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_unit_of_work_is_created(self):
        """
        Create a UnitOfWork and store its repository instances on the scenario.
        
        Sets the following scenario attributes from the UnitOfWork:
        - mr_repo: merge requests repository
        - history_repo: history repository
        - analytics_repo: analytics repository
        """
        async with UnitOfWork(self.db) as uow:
            self.mr_repo = uow.merge_requests
            self.history_repo = uow.history
            self.analytics_repo = uow.analytics

    def then_merge_requests_should_be_available(self):
        """
        Assert that the scenario's merge request repository is available and is a MergeRequestRepository.
        
        Raises:
            AssertionError: If `self.mr_repo` is not an instance of MergeRequestRepository.
        """
        assert isinstance(self.mr_repo, MergeRequestRepository)

    def and_history_should_be_available(self):
        """
        Verify that the scenario's history repository is an instance of HistoryRepository.
        """
        assert isinstance(self.history_repo, HistoryRepository)

    def and_analytics_should_be_available(self):
        """
        Verify that the scenario exposes an AnalyticsRepository instance.
        
        Raises:
            AssertionError: If self.analytics_repo is not an instance of AnalyticsRepository.
        """
        assert isinstance(self.analytics_repo, AnalyticsRepository)

    async def do_cleanup(self):
        """
        Exit the test database async context to clean up test resources.
        
        This closes the previously entered database context manager obtained during setup.
        """
        await self._db_ctx.__aexit__(None, None, None)
