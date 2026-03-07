"""Test scenario for successful MR processing flow.

This scenario tests the happy path where an MR is successfully:
1. Rebased
2. Tested (pipeline passes)
3. Merged

Tests `_execute_workflow` with FakeStateMachine starting in "queued" state.
"""

from __future__ import annotations

from datetime import UTC, datetime

from vedro import given, scenario, then, when

from gitlab_queue.core.processor import ProcessingContext, ProcessingResult
from scenarios.fakes import FakeCurrentState, FakeStateMachine, create_mr, create_pipeline
from scenarios.unit.processor._helpers import (
    create_mock_processor,
    create_test_queue_item,
    instant_poll,
)


@scenario()
async def process_mr_successfully_from_queue_to_merge():
    """Test full happy path: queued -> rebasing -> testing -> merging -> merged."""

    with given("a processor with faked collaborators and an MR in queue"):
        mr = create_mr(
            iid=42,
            sha="abc123",
            labels=["merge_queue"],
            state="opened",
            source_branch="feature/test",
        )

        pipeline = create_pipeline(id=1001, sha="abc123", status="success")

        sm = FakeStateMachine(current_state=FakeCurrentState(id="queued"))
        processor = create_mock_processor(poll_fn=instant_poll)

        # Same SHA as post-rebase pipeline: simulates fast-forward rebase (no new commits)
        pre_rebase_pipeline = create_pipeline(id=1000, sha="abc123", status="success")

        # MR responses consumed in order:
        # 1. _capture_pre_rebase_state (in _process_rebase)
        # 2. _wait_for_post_rebase_pipeline -> check_pipeline -> get_mr
        # 3. _verify_mr_in_queue (in _check_pipeline_termination_conditions)
        processor.gitlab_client.mr_response_sequence = [mr, mr, mr]

        # Pipeline responses consumed in order:
        # 1. _capture_pre_rebase_state -> get_latest_mr_pipeline (old pipeline)
        # 2. _wait_for_post_rebase_pipeline -> get_latest_mr_pipeline (new pipeline)
        # 3. _wait_for_pipeline loop -> get_latest_mr_pipeline
        processor.gitlab_client.latest_pipeline_sequence = [pre_rebase_pipeline, pipeline, pipeline]

        # Merge result
        processor.gitlab_client.merge_result = create_mr(iid=42, state="merged")

        # Queue item needed by _should_skip_stale_pipeline and _handle_pipeline_status
        queue_item = create_test_queue_item(mr_iid=42, state="queued")
        processor.queue_manager.add_item(queue_item)

        ctx = ProcessingContext(
            mr_iid=42,
            state_machine=sm,
            start_time=datetime.now(UTC),
        )

    with when("processor executes the full workflow"):
        result = await processor._execute_workflow(ctx)

    with then("result is SUCCESS"):
        assert result == ProcessingResult.SUCCESS

    with then("merge was called exactly once"):
        assert len(processor.gitlab_client.merge_calls) == 1

    with then("state machine received merge_success trigger"):
        assert len(sm.merge_success_calls) == 1

    with then("rebase was initiated"):
        assert len(processor.gitlab_client.rebase_calls) == 1

    with then("state machine transitioned through all expected states"):
        # start_processing: queued -> rebasing
        assert len(sm.start_processing_calls) == 1
        # rebase_complete: rebasing -> testing
        assert len(sm.rebase_complete_calls) == 1
        # pipeline_success: testing -> merging
        assert len(sm.pipeline_success_calls) == 1
        # merge_success: merging -> merged
        assert sm.current_state.id == "merged"


__all__ = [
    "process_mr_successfully_from_queue_to_merge",
]
