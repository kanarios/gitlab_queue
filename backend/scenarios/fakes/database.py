from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from gitlab_queue.db.database import DatabaseStatus

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable


@dataclass
class FakeSession:
    """Fake SQLAlchemy async session for QueueManager tests."""

    execute_fn: Callable[..., Awaitable[Any]] | None = None
    execute_calls: list[tuple[Any, ...]] = field(default_factory=list)

    async def execute(self, sql: Any, params: Any = None) -> Any:
        self.execute_calls.append((sql, params))
        if self.execute_fn is not None:
            return await self.execute_fn(sql, params)
        return FakeResult()

    async def commit(self) -> None:
        pass


@dataclass
class FakeResult:
    """Fake SQLAlchemy result object."""

    _row_data: dict[str, Any] | None = None

    def mappings(self) -> FakeResult:
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        return self._row_data


@dataclass
class FakeDatabase:
    connected: bool = True
    wal_mode: bool = True
    error: str | None = None

    _transaction_sessions: list[FakeSession] = field(default_factory=list)
    _session_sessions: list[FakeSession] = field(default_factory=list)
    _transaction_index: int = field(default=0)
    _session_index: int = field(default=0)

    async def health_check(self) -> DatabaseStatus:
        return DatabaseStatus(
            connected=self.connected,
            wal_mode_enabled=self.wal_mode,
            foreign_keys_enabled=True,
            database_path="sqlite+aiosqlite:///:memory:",
            error=self.error,
        )

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[FakeSession]:
        if self._transaction_sessions:
            if self._transaction_index >= len(self._transaction_sessions):
                raise AssertionError(
                    f"FakeDatabase: no more transaction sessions "
                    f"(seeded {len(self._transaction_sessions)}, requested #{self._transaction_index + 1})"
                )
            session = self._transaction_sessions[self._transaction_index]
            self._transaction_index += 1
        else:
            session = FakeSession()
        yield session

    @asynccontextmanager
    async def session(self) -> AsyncIterator[FakeSession]:
        if self._session_sessions:
            if self._session_index >= len(self._session_sessions):
                raise AssertionError(
                    f"FakeDatabase: no more read sessions "
                    f"(seeded {len(self._session_sessions)}, requested #{self._session_index + 1})"
                )
            session = self._session_sessions[self._session_index]
            self._session_index += 1
        else:
            session = FakeSession()
        yield session
