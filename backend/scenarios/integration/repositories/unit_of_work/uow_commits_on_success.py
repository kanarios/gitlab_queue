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
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_mr_is_added_via_uow_with_auto_commit(self):
        async with UnitOfWork(self.db, auto_commit=True) as uow:
            mr = create_test_mr_model(iid=42, title="UoW Test MR")
            await uow.merge_requests.add(mr)

    async def then_mr_should_be_persisted(self):
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            result = await repo.get_by_iid(42)
            assert result is not None
            assert result.title == "UoW Test MR"

    async def do_cleanup(self):
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
