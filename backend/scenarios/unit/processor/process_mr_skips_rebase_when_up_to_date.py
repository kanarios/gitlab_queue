"""Test full MR processing flow when the MR is already up-to-date with target.

The MR has zero diverged commits, so the rebase API is never called and the
existing pipeline on the MR's SHA is used for testing:
queued -> rebasing (no-op) -> testing -> merging -> merged.
"""

from __future__ import annotations

from vedro import given, scenario, then, when

from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import FakeCurrentState, FakeStateMachine, create_mr, create_pipeline
from scenarios.unit.processor._helpers import (
    create_mock_processor,
    create_processing_context,
    create_test_queue_item,
    instant_poll,
)


@scenario()
async def process_mr_skips_rebase_when_up_to_date():
    """Test happy path without rebase: existing pipeline is reused through to merge."""

    with given("a processor and an up-to-date MR with a successful pipeline"):
        mr = create_mr(iid=42, sha="abc123", source_branch="feature/test", diverged_commits_count=0)
        pipeline = create_pipeline(id=1000, sha="abc123", status="success")

        sm = FakeStateMachine(current_state=FakeCurrentState(id="queued"))
        processor = create_mock_processor(poll_fn=instant_poll)

        # MR responses consumed in order:
        # 1. pre-rebase state capture (in _process_rebase)
        # 2. _verify_mr_in_queue (in _check_pipeline_termination_conditions)
        processor.gitlab_client.mr_response_sequence = [mr, mr]

        # Pipeline responses consumed in order:
        # 1. pre-rebase state capture -> reused for testing
        # 2. _wait_for_pipeline loop
        processor.gitlab_client.latest_pipeline_sequence = [pipeline, pipeline]

        processor.gitlab_client.merge_result = create_mr(iid=42, state="merged")
        processor.queue_manager.add_item(create_test_queue_item(mr_iid=42, state="queued"))

        ctx = create_processing_context(mr_iid=42, state_machine=sm)

    with when("processor executes the full workflow"):
        result = await processor._execute_workflow(ctx)

    with then("result is SUCCESS"):
        assert result == ProcessingResult.SUCCESS

    with then("rebase was never initiated"):
        assert processor.gitlab_client.rebase_calls == []

    with then("no new pipeline was created"):
        assert processor.gitlab_client.create_pipeline_calls == []

    with then("testing started with the existing pipeline"):
        assert sm.rebase_complete_calls[0]["pipeline_id"] == 1000
        assert sm.rebase_complete_calls[0]["expected_sha"] == "abc123"

    with then("MR was merged"):
        assert len(processor.gitlab_client.merge_calls) == 1
        assert sm.current_state.id == "merged"


__all__ = [
    "process_mr_skips_rebase_when_up_to_date",
]
