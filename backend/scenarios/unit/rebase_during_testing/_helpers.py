"""Helpers for rebase_during_testing module test scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

from gitlab_queue.core.rebase_during_testing import (
    RebaseDuringTestingContext,
    RebaseDuringTestingHandler,
)


@dataclass
class MockMergeRequest:
    """Mock MR for testing."""

    iid: int = 42
    sha: str = "abc123"
    merge_status: str = "can_be_merged"
    has_conflicts: bool = False
    rebase_in_progress: bool = False


@dataclass
class MockPipeline:
    """Mock Pipeline for testing."""

    id: int = 100
    sha: str = "abc123"
    status: str = "running"


@dataclass
class MockSettings:
    """Mock Settings for testing."""

    rebase_timeout_seconds: float = 60.0
    post_rebase_pipeline_wait_seconds: float = 30.0
    pipeline_poll_interval_seconds: float = 5.0


def create_mock_gitlab_client(
    mr: MockMergeRequest | None = None,
    pipeline: MockPipeline | None = None,
) -> MagicMock:
    """Create mock GitLabClient."""
    client = MagicMock()
    client.get_mr = AsyncMock(return_value=mr or MockMergeRequest())
    client.get_latest_mr_pipeline = AsyncMock(return_value=pipeline)
    client.cancel_pipeline = AsyncMock()
    client.rebase_mr = AsyncMock()
    client.check_rebase_status = AsyncMock(return_value=(False, False))
    return client


def create_handler(
    gitlab_client: MagicMock | None = None,
    settings: MockSettings | None = None,
) -> RebaseDuringTestingHandler:
    """Create RebaseDuringTestingHandler for tests."""
    return RebaseDuringTestingHandler(
        gitlab_client=gitlab_client or create_mock_gitlab_client(),
        settings=settings or MockSettings(),
    )


def create_context(
    rebase_count: int = 0,
    max_attempts: int = 3,
    current_pipeline_id: int | None = None,
) -> RebaseDuringTestingContext:
    """Create RebaseDuringTestingContext for tests."""
    return RebaseDuringTestingContext(
        rebase_count=rebase_count,
        max_attempts=max_attempts,
        current_pipeline_id=current_pipeline_id,
    )


__all__ = [
    "MockMergeRequest",
    "MockPipeline",
    "MockSettings",
    "create_context",
    "create_handler",
    "create_mock_gitlab_client",
]
