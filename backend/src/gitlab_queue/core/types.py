"""Shared types for the merge queue core module.

Contains result types, context objects, and signal dataclasses
used across processor, pipeline_handler, and rebase_handler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from gitlab_queue.core.protocols import StateMachineProtocol
    from gitlab_queue.core.rebase_during_testing import RebaseDuringTestingContext


class ProcessingResult(Enum):
    """Result of processing a single MR."""

    SUCCESS = "success"  # MR merged successfully
    CONFLICT = "conflict"  # Rebase failed due to conflicts
    PIPELINE_FAILED = "pipeline_failed"  # Pipeline failed after retries
    MERGE_FAILED = "merge_failed"  # Merge operation failed
    TIMEOUT = "timeout"  # Operation timed out
    REMOVED = "removed"  # MR removed during processing
    ERROR = "error"  # Unexpected error


@dataclass
class RebaseContext:
    """Context for rebase operation tracking.

    Tracks SHA before rebase to detect race conditions where
    GitLab returns stale pipeline data after rebase completes.
    """

    old_sha: str = ""
    old_pipeline_id: int | None = None


@dataclass
class ProcessingContext:
    """Context for current MR processing."""

    mr_iid: int
    state_machine: StateMachineProtocol
    start_time: datetime
    rebase_ctx: RebaseContext = field(default_factory=RebaseContext)


@dataclass
class RebaseCheckOutcome:
    """Result of checking if rebase is needed during testing.

    Separates success context from error result for clearer API.
    """

    context: RebaseDuringTestingContext | None
    result: ProcessingResult | None
    last_check: datetime
    should_reset: bool


@dataclass
class RetrySignal:
    """Signal to retry pipeline with updated per-job retry state.

    Used instead of tuple[dict, datetime] for type clarity.
    """

    retried_jobs: dict[str, int]
    new_start_time: datetime | None


__all__: list[str] = [
    "ProcessingContext",
    "ProcessingResult",
    "RebaseCheckOutcome",
    "RebaseContext",
    "RetrySignal",
]
