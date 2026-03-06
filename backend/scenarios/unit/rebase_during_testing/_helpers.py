"""Helpers for rebase_during_testing module test scenarios."""

from __future__ import annotations

from dataclasses import dataclass

from gitlab_queue.core.rebase_during_testing import (
    RebaseDuringTestingContext,
    RebaseDuringTestingHandler,
)
from scenarios.fakes import FakeGitLabClient, create_mr, create_pipeline


@dataclass
class MockMergeRequest:
    """Typed MR stub for testing."""

    iid: int = 42
    sha: str = "abc123"
    merge_status: str = "can_be_merged"
    has_conflicts: bool = False
    rebase_in_progress: bool = False


@dataclass
class MockPipeline:
    """Typed Pipeline stub for testing."""

    id: int = 100
    sha: str = "abc123"
    status: str = "running"


@dataclass
class MockSettings:
    """Typed Settings stub for testing."""

    rebase_timeout_seconds: float = 60.0
    post_rebase_pipeline_wait_seconds: float = 30.0
    pipeline_poll_interval_seconds: float = 5.0


def create_mock_gitlab_client(
    mr: MockMergeRequest | None = None,
    pipeline: MockPipeline | None = None,
) -> FakeGitLabClient:
    """Create a FakeGitLabClient configured with mock MR and pipeline data."""
    mock_mr = mr or MockMergeRequest()
    real_mr = create_mr(
        iid=mock_mr.iid,
        sha=mock_mr.sha,
        merge_status=mock_mr.merge_status,
        has_conflicts=mock_mr.has_conflicts,
        rebase_in_progress=mock_mr.rebase_in_progress,
    )

    latest_pipeline = None
    if pipeline is not None:
        latest_pipeline = create_pipeline(
            id=pipeline.id,
            sha=pipeline.sha,
            status=pipeline.status,
        )

    return FakeGitLabClient(
        mr_responses={mock_mr.iid: real_mr},
        latest_pipeline_response=latest_pipeline,
    )


def create_handler(
    gitlab_client: FakeGitLabClient | None = None,
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
