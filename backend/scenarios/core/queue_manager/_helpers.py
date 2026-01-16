"""Helpers for QueueManager test scenarios."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from gitlab_queue.models.mr import Author, MergeRequest
from scenarios.library import Labels, MRState, QueueState


def create_mock_database() -> tuple[MagicMock, AsyncMock, AsyncMock]:
    """Create a mock database with async context managers."""
    db = MagicMock()

    # Create async context managers for session and transaction
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock()
    session_cm.__aexit__ = AsyncMock(return_value=None)

    transaction_cm = AsyncMock()
    transaction_cm.__aenter__ = AsyncMock()
    transaction_cm.__aexit__ = AsyncMock(return_value=None)

    db.session.return_value = session_cm
    db.transaction.return_value = transaction_cm

    return db, session_cm, transaction_cm


def create_test_mr(iid: int = 123, title: str = "Test MR") -> MergeRequest:
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
    )


def create_mock_row(
    iid: int = 123,
    status: str = QueueState.QUEUED,
    is_hotfix: int = 0,
) -> dict:
    """Create a mock database row."""
    return {
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
