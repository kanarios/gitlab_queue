"""Helpers for QueueManager test scenarios."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from scenarios.library import Labels, MRState, QueueState

from gitlab_queue.models.mr import Author, MergeRequest


class _FakeSession:
    """Async session stub with a configurable execute result."""

    def __init__(self) -> None:
        self.execute_result: Any = None

    async def execute(self, stmt: Any, params: Any = None) -> Any:
        return self.execute_result

    async def commit(self) -> None:
        pass


class _FakeAsyncCtx:
    """Async context manager that yields a given value."""

    def __init__(self, value: Any) -> None:
        self._value = value

    async def __aenter__(self) -> Any:
        return self._value

    async def __aexit__(self, *args: Any) -> None:
        pass


class FakeMockDatabase:
    """Lightweight database stub for QueueManager tests.

    Provides session() and transaction() as async context managers
    that yield FakeSession instances.
    """

    def __init__(self) -> None:
        self.session_obj = _FakeSession()
        self.transaction_obj = _FakeSession()

    def session(self) -> _FakeAsyncCtx:
        return _FakeAsyncCtx(self.session_obj)

    def transaction(self) -> _FakeAsyncCtx:
        return _FakeAsyncCtx(self.transaction_obj)


def create_mock_database() -> tuple[FakeMockDatabase, _FakeSession, _FakeSession]:
    """Create a fake database with async context managers."""
    db = FakeMockDatabase()
    return db, db.session_obj, db.transaction_obj


def create_test_mr(
    iid: int = 123,
    title: str = "Test MR",
    project_id: int = 99999,
) -> MergeRequest:
    """Create a test MergeRequest."""
    return MergeRequest(
        iid=iid,
        title=title,
        state=MRState.OPENED,
        labels=[Labels.FEATURE],
        sha="abc123",
        source_branch="feature",
        target_branch="master",
        merge_status="can_be_merged",
        author=Author(id=1, name="Test User", username="testuser"),
        project_id=project_id,
    )


def create_mock_row(
    iid: int = 123,
    status: str = QueueState.QUEUED,
    is_hotfix: int = 0,
    project_id: int = 99999,
) -> dict:
    """Create a mock database row."""
    return {
        "project_id": project_id,
        "iid": iid,
        "title": "Test MR",
        "author_name": "Test User",
        "author_username": "testuser",
        "author_avatar": None,
        "status": status,
        "is_hotfix": is_hotfix,
        "labels": "[]",
        "target_branch": "master",
        "queued_at": datetime.now(UTC).isoformat(),
        "started_at": None,
        "finished_at": None,
        "pipeline_id": None,
        "pipeline_status": None,
        "retry_count": 0,
        "last_error": None,
    }
