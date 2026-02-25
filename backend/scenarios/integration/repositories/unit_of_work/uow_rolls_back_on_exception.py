"""Test that UnitOfWork rolls back on exception."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import (
    create_tables,
    create_test_mr_model,
)

from gitlab_queue.db.repositories import MergeRequestRepository, UnitOfWork


class Scenario(vedro.Scenario):
    subject = "unit of work rolls back on exception"

    async def given_initialized_database(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_exception_occurs_inside_uow(self):
        try:
            async with UnitOfWork(self.db, auto_commit=True) as uow:
                mr = create_test_mr_model(iid=42, title="Should Not Persist")
                await uow.merge_requests.add(mr)
                raise ValueError("Simulated failure")
        except ValueError as exc:
            self.caught_exc = exc

    def then_caught_exception_is_simulated_failure(self):
        assert str(self.caught_exc) == "Simulated failure"

    async def and_mr_should_not_be_persisted(self):
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            result = await repo.get_by_iid(42)
            assert result is None

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
