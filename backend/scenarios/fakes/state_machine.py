from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeCurrentState:
    id: str = "queued"


@dataclass
class FakeStateMachine:
    current_state: FakeCurrentState = field(default_factory=FakeCurrentState)

    # Call recording for triggers
    start_processing_calls: list[dict[str, Any]] = field(default_factory=list)
    rebase_complete_calls: list[dict[str, Any]] = field(default_factory=list)
    rebase_failed_calls: list[dict[str, Any]] = field(default_factory=list)
    conflict_during_testing_calls: list[dict[str, Any]] = field(default_factory=list)
    pipeline_success_calls: list[dict[str, Any]] = field(default_factory=list)
    pipeline_failed_calls: list[dict[str, Any]] = field(default_factory=list)
    merge_success_calls: list[dict[str, Any]] = field(default_factory=list)
    merge_failed_calls: list[dict[str, Any]] = field(default_factory=list)
    mark_removed_calls: list[dict[str, Any]] = field(default_factory=list)
    timeout_calls: list[dict[str, Any]] = field(default_factory=list)

    # Call recording for notifications
    pipeline_retry_calls: list[dict[str, Any]] = field(default_factory=list)
    position_changed_calls: list[dict[str, Any]] = field(default_factory=list)
    rebase_complete_notify_calls: list[dict[str, Any]] = field(default_factory=list)
    stale_warning_calls: list[dict[str, Any]] = field(default_factory=list)
    rebase_during_testing_calls: list[dict[str, Any]] = field(default_factory=list)

    # Error injection
    trigger_errors: dict[str, Exception] = field(default_factory=dict)

    async def trigger_start_processing(self) -> None:
        self._check_error("start_processing")
        self.start_processing_calls.append({})
        self.current_state.id = "rebasing"

    async def trigger_rebase_complete(
        self,
        *,
        pipeline_id: int,
        pipeline_url: str,
        expected_sha: str | None = None,
    ) -> None:
        self._check_error("rebase_complete")
        self.rebase_complete_calls.append(
            {
                "pipeline_id": pipeline_id,
                "pipeline_url": pipeline_url,
                "expected_sha": expected_sha,
            }
        )
        self.current_state.id = "testing"

    async def trigger_rebase_failed(self, *, conflicted_files: list[str], error_message: str) -> None:
        self._check_error("rebase_failed")
        self.rebase_failed_calls.append(
            {
                "conflicted_files": conflicted_files,
                "error_message": error_message,
            }
        )
        self.current_state.id = "failed"

    async def trigger_conflict_during_testing(self, *, conflicted_files: list[str], error_message: str) -> None:
        self._check_error("conflict_during_testing")
        self.conflict_during_testing_calls.append(
            {
                "conflicted_files": conflicted_files,
                "error_message": error_message,
            }
        )
        self.current_state.id = "failed"

    async def trigger_pipeline_success(self) -> None:
        self._check_error("pipeline_success")
        self.pipeline_success_calls.append({})
        self.current_state.id = "merging"

    async def trigger_pipeline_failed(self, *, failed_jobs: list[str], retry_count: int, error_message: str) -> None:
        self._check_error("pipeline_failed")
        self.pipeline_failed_calls.append(
            {
                "failed_jobs": failed_jobs,
                "retry_count": retry_count,
                "error_message": error_message,
            }
        )
        self.current_state.id = "failed"

    async def trigger_merge_success(self) -> None:
        self._check_error("merge_success")
        self.merge_success_calls.append({})
        self.current_state.id = "merged"

    async def trigger_merge_failed(self, *, error_message: str) -> None:
        self._check_error("merge_failed")
        self.merge_failed_calls.append({"error_message": error_message})
        self.current_state.id = "failed"

    async def trigger_mark_removed(self, *, reason: str = "label_removed") -> None:
        self._check_error("mark_removed")
        self.mark_removed_calls.append({"reason": reason})
        self.current_state.id = "removed"

    async def trigger_timeout(self, *, max_wait_hours: int = 2) -> None:
        self._check_error("timeout")
        self.timeout_calls.append({"max_wait_hours": max_wait_hours})
        self.current_state.id = "failed"

    async def notify_pipeline_retry(
        self,
        *,
        old_pipeline_id: int,
        old_pipeline_url: str,
        new_pipeline_id: int,
        new_pipeline_url: str,
        retry_count: int,
        max_retries: int,
        failed_jobs: list[str],
        expected_sha: str | None = None,
    ) -> None:
        self.pipeline_retry_calls.append(
            {
                "old_pipeline_id": old_pipeline_id,
                "old_pipeline_url": old_pipeline_url,
                "new_pipeline_id": new_pipeline_id,
                "new_pipeline_url": new_pipeline_url,
                "retry_count": retry_count,
                "max_retries": max_retries,
                "failed_jobs": failed_jobs,
                "expected_sha": expected_sha,
            }
        )

    async def notify_position_changed(self, *, old_position: int) -> None:
        self.position_changed_calls.append({"old_position": old_position})

    async def notify_rebase_complete(self) -> None:
        self.rebase_complete_notify_calls.append({})

    async def notify_stale_warning(self, *, warning_hours: int) -> None:
        self.stale_warning_calls.append({"warning_hours": warning_hours})

    async def notify_rebase_during_testing(
        self,
        *,
        old_pipeline_id: int | None,
        new_pipeline_id: int,
        rebase_count: int,
        max_attempts: int,
    ) -> None:
        self.rebase_during_testing_calls.append(
            {
                "old_pipeline_id": old_pipeline_id,
                "new_pipeline_id": new_pipeline_id,
                "rebase_count": rebase_count,
                "max_attempts": max_attempts,
            }
        )

    def _check_error(self, trigger_name: str) -> None:
        if trigger_name in self.trigger_errors:
            raise self.trigger_errors[trigger_name]


@dataclass
class FakeStateMachineFactory:
    state_machine: FakeStateMachine = field(default_factory=FakeStateMachine)
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def __call__(
        self,
        mr_iid: int,
        notifier: Any,
        queue_manager: Any,
        **kwargs: Any,
    ) -> FakeStateMachine:
        self.calls.append(
            {
                "mr_iid": mr_iid,
                "notifier": notifier,
                "queue_manager": queue_manager,
                **kwargs,
            }
        )
        return self.state_machine
