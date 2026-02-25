"""Test that add creates a new record in the database."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import (
    create_tables,
    create_test_mr_model,
)

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "add creates a new merge request record"

    async def given_empty_database(self):
        """
        Set up an initialized test database context and prepare schema for the scenario.
        
        Creates an asynchronous test database context, enters it, assigns the context to `self._db_ctx` and the active session to `self.db`, and ensures required tables exist.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_mr_is_added(self):
        """
        Prepare and add a test merge request to the repository, storing the persisted result on self.added_mr.
        
        Creates a test MergeRequest model with iid=42 and title="New MR", adds it through MergeRequestRepository within a transactional session, and assigns the persisted model returned by the repository to self.added_mr.
        """
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            mr = create_test_mr_model(iid=42, title="New MR")
            self.added_mr = await repo.add(mr)

    def then_added_mr_should_have_an_id(self):
        """
        Asserts that the recently added merge request has been persisted by checking it has an assigned id.
        
        Raises an AssertionError if `self.added_mr.id` is None.
        """
        assert self.added_mr.id is not None

    async def and_mr_should_be_in_database(self):
        """
        Asserts that a merge request with IID 42 exists in the database and has the title "New MR".
        
        Opens a database session, retrieves the merge request by IID 42, and fails the test if the record is missing or its title differs.
        """
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            result = await repo.get_by_iid(42)
            assert result is not None
            assert result.title == "New MR"

    async def do_cleanup(self):
        """
        Exit the test database context and release associated resources.
        
        This method awaits the asynchronous exit of the internal database context manager to clean up connections and temporary state established for the scenario.
        """
        await self._db_ctx.__aexit__(None, None, None)
