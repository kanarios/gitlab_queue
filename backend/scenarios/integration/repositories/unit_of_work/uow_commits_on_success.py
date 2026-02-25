"""Test that UnitOfWork with auto_commit commits on success."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import (
    create_tables,
    create_test_mr_model,
)

from gitlab_queue.db.repositories import MergeRequestRepository, UnitOfWork


class Scenario(vedro.Scenario):
    subject = "unit of work commits on success with auto_commit"

    async def given_initialized_database(self):
        """
        Initialize an in-memory test database, enter its async context, and create required tables.
        
        This stores the async database context manager on `self._db_ctx` and the opened database handle on `self.db` for use by subsequent test steps.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_mr_is_added_via_uow_with_auto_commit(self):
        """
        Adds a test merge request to the database using a UnitOfWork configured to auto-commit on success.
        
        Creates a merge request model with iid=42 and title "UoW Test MR" and adds it to the unit's merge_requests repository; the UnitOfWork's auto-commit will persist the change when the context is exited if no errors occur.
        """
        async with UnitOfWork(self.db, auto_commit=True) as uow:
            mr = create_test_mr_model(iid=42, title="UoW Test MR")
            await uow.merge_requests.add(mr)

    async def then_mr_should_be_persisted(self):
        """
        Verify that a merge request with iid 42 was persisted and has the expected title.
        
        Asserts that the repository returns a MergeRequest with iid 42 and that its title equals "UoW Test MR".
        """
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            result = await repo.get_by_iid(42)
            assert result is not None
            assert result.title == "UoW Test MR"

    async def do_cleanup(self):
        """
        Release the initialized test database context and free associated resources.
        
        Closes the asynchronous database context manager obtained during setup so the test database connection and related resources are cleaned up.
        """
        await self._db_ctx.__aexit__(None, None, None)
