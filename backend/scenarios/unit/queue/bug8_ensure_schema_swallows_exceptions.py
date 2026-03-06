"""BUG-8: ensure_schema swallows all ALTER TABLE exceptions."""

from __future__ import annotations

from typing import Any

import vedro
from sqlalchemy.exc import OperationalError

from gitlab_queue.core.queue import QueueManager


class _FakeMappingsResult:
    def mappings(self) -> _FakeMappingsResult:
        return self

    def all(self) -> list:
        return []


class _FakeSession:
    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario

    async def execute(self, stmt: Any, *_args: Any, **_kwargs: Any) -> Any:
        self._scenario.execute_call_count += 1
        sql_text = str(stmt)
        if "ALTER TABLE" in sql_text:
            raise OperationalError(
                statement="ALTER TABLE ...",
                params={},
                orig=Exception("disk I/O error"),
            )
        return _FakeMappingsResult()


class _FakeTransactionCtx:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, *args: Any) -> bool:
        return False


class _FakeDB:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def transaction(self) -> _FakeTransactionCtx:
        return _FakeTransactionCtx(self._session)


class Scenario(vedro.Scenario):
    subject = "ensure_schema re-raises non-duplicate-column errors"

    def given_queue_manager_with_failing_alter_table(self):
        self.execute_call_count = 0
        session = _FakeSession(self)
        self.db = _FakeDB(session)
        self.queue = QueueManager(db=self.db)

    async def when_ensure_schema_is_called(self):
        self.raised = None
        try:
            await self.queue.ensure_schema()
        except OperationalError as e:
            self.raised = e

    def then_non_duplicate_error_should_be_raised(self):
        assert self.raised is not None, "Expected OperationalError to be raised"
        assert "disk I/O error" in str(self.raised)
