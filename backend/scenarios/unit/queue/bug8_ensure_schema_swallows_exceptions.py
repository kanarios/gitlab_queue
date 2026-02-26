"""BUG-8: ensure_schema swallows all ALTER TABLE exceptions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from sqlalchemy.exc import OperationalError

from gitlab_queue.core.queue import QueueManager


class Scenario(vedro.Scenario):
    subject = "ensure_schema re-raises non-duplicate-column errors"

    def given_queue_manager_with_failing_alter_table(self):
        self.db = MagicMock()
        self.queue = QueueManager(db=self.db)

        # Track call count to distinguish ALTER TABLE calls
        self.execute_call_count = 0

        async def mock_execute(stmt, *_args, **_kwargs):
            self.execute_call_count += 1
            sql_text = str(stmt)
            if "ALTER TABLE" in sql_text:
                # Simulate a real error (not duplicate column)
                raise OperationalError(
                    statement="ALTER TABLE ...",
                    params={},
                    orig=Exception("disk I/O error"),
                )
            return MagicMock(mappings=lambda: MagicMock(all=lambda: []))

        # Create async context manager mock for transaction
        session = MagicMock()
        session.execute = mock_execute

        ctx_manager = MagicMock()
        ctx_manager.__aenter__ = AsyncMock(return_value=session)
        ctx_manager.__aexit__ = AsyncMock(return_value=False)
        self.db.transaction = MagicMock(return_value=ctx_manager)

    async def when_ensure_schema_is_called(self):
        self.raised = None
        try:
            await self.queue.ensure_schema()
        except OperationalError as e:
            self.raised = e

    def then_non_duplicate_error_should_be_raised(self):
        assert self.raised is not None, "Expected OperationalError to be raised"
        assert "disk I/O error" in str(self.raised)
