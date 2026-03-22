"""Integration test scenarios for complete end-to-end flow.

Tests processor._process_mr through multiple failure/recovery scenarios
using real QueueManager (SQLite) and Fakes for GitLab/notifier.

Note: The following scenarios have been extracted to separate files:
- full_flow_hotfix.py - Hotfix priority testing
- full_flow_restart.py - System restart and recovery
- full_flow_concurrent.py - Concurrent operations and race conditions
"""

from __future__ import annotations

from typing import Any

from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.fakes import (
    FakeCurrentState,
    FakeGitLabClient,
    FakeNotifier,
    FakeSettings,
    FakeStateMachine,
    create_job,
    create_mr,
    create_pipeline,
)
from vedro import given, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabConflictError
from gitlab_queue.core.processor import MergeProcessor, ProcessingResult
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.models.mr import Author, MergeRequest


def _make_mr(iid: int, title: str, sha: str) -> MergeRequest:
    return create_mr(
        iid=iid,
        title=title,
        sha=sha,
        state="opened",
        labels=["merge_queue"],
        target_branch="main",
        source_branch=f"feature/{iid}",
        author=Author(id=iid, name=f"User {iid}", username=f"user{iid}"),
    )


@scenario()
async def full_flow_with_failures_and_recovery():
    """Test complete flow with failures and recovery mechanisms."""

    async with initialized_test_database() as db:
        with given("system with various failure scenarios"):
            queue = QueueManager(db)
            await queue.ensure_schema()

            mr_400 = _make_mr(400, "Flaky Pipeline", "flaky123")
            mr_402 = _make_mr(402, "Conflict MR", "conflict123")

            settings_pid = FakeSettings().gitlab_project_id
            await queue.add_to_queue(settings_pid, mr_400, is_hotfix=False)
            await queue.add_to_queue(settings_pid, mr_402, is_hotfix=False)

            # Per-MR state machines
            state_machines: dict[int, FakeStateMachine] = {}

            async def sm_factory(project_id: int, mr_iid: int, **_: Any) -> FakeStateMachine:
                sm = FakeStateMachine(current_state=FakeCurrentState(id="queued"))
                state_machines[mr_iid] = sm
                return sm

            # MR 400: flaky pipeline (fail → job retry → success → merge)
            # Pipeline sequence consumed by:
            #   1. capture_pre_rebase_state → old pipeline before rebase
            #   2. post-rebase wait (fast-forward): sees "running" → returns it
            #   3. wait_for_pipeline poll 1: sees "failed" → job retry
            #   4. wait_for_pipeline poll 2: sees "success" → merge
            gitlab_400 = FakeGitLabClient(
                mr_responses={400: mr_400},
                latest_pipeline_sequence=[
                    create_pipeline(id=7999, status="success", sha="flaky123"),
                    create_pipeline(id=8000, status="running", sha="flaky123"),
                    create_pipeline(id=8000, status="failed", sha="flaky123"),
                    create_pipeline(id=8000, status="success", sha="flaky123"),
                ],
                pipeline_jobs_response=[create_job(id=9000, name="test", status="failed")],
            )

            processor_400 = MergeProcessor(
                gitlab_client=gitlab_400,
                queue_manager=queue,
                notifier=FakeNotifier(),
                settings=FakeSettings(
                    job_retry_count=2,
                    pipeline_timeout_seconds=10,
                    pipeline_poll_interval_seconds=0.01,
                ),
                state_machine_factory=sm_factory,
            )

            # MR 402: conflict on rebase
            gitlab_402 = FakeGitLabClient(
                mr_responses={402: mr_402},
                rebase_mr_error=GitLabConflictError("Conflict"),
                mr_conflicts=["file.py"],
            )

            processor_402 = MergeProcessor(
                gitlab_client=gitlab_402,
                queue_manager=queue,
                notifier=FakeNotifier(),
                settings=FakeSettings(),
                state_machine_factory=sm_factory,
            )

        with when("system handles various failure scenarios"):
            results: list[tuple[int, ProcessingResult]] = []

            queue_item = await queue.get_next_mr(settings_pid)
            assert queue_item is not None and queue_item.mr_iid == 400
            result_400 = await processor_400._process_mr(queue_item)
            results.append((400, result_400))

            queue_item = await queue.get_next_mr(settings_pid)
            assert queue_item is not None and queue_item.mr_iid == 402
            result_402 = await processor_402._process_mr(queue_item)
            results.append((402, result_402))

        with then("flaky pipeline succeeds after job retry"):
            assert results[0][1] == ProcessingResult.SUCCESS
            assert len(gitlab_400.merge_calls) == 1
            assert len(gitlab_400.retry_job_calls) == 1

        with then("conflict MR is detected and fails"):
            assert results[1][1] == ProcessingResult.CONFLICT
            sm_402 = state_machines[402]
            assert len(sm_402.rebase_failed_calls) == 1
            assert sm_402.rebase_failed_calls[0]["conflicted_files"] == ["file.py"]


__all__ = [
    "full_flow_with_failures_and_recovery",
]
