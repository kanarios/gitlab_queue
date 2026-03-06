"""Test scenario: _wait_for_rebase completes when rebase finishes without conflicts.

Verifies that when check_rebase_status returns (False, False) — rebase completed,
no conflicts — the processor finds the post-rebase pipeline and triggers
rebase_complete on the state machine.
"""

from __future__ import annotations

from datetime import UTC, datetime

from vedro import given, scenario, then, when

from gitlab_queue.core.processor import ProcessingContext, ProcessingResult, RebaseContext
from scenarios.fakes import FakeCurrentState, FakeStateMachine, create_mr, create_pipeline
from scenarios.unit.processor._helpers import (
    create_mock_processor,
    instant_poll,
)


@scenario()
async def process_mr_with_async_rebase():
    with given("processor with completed rebase and post-rebase pipeline"):
        sm = FakeStateMachine(current_state=FakeCurrentState(id="rebasing"))
        processor = create_mock_processor(poll_fn=instant_poll)

        # MR returned by get_mr inside _wait_for_post_rebase_pipeline
        mr = create_mr(iid=43, sha="def456", labels=["merge_queue"], state="opened")
        processor.gitlab_client.mr_response_sequence = [mr]

        # Rebase completes (not in progress, no conflicts)
        processor.gitlab_client.rebase_status = (False, False)

        # Pipeline found after rebase (fast-forward case: old_sha == new_sha)
        pipeline = create_pipeline(id=1002, sha="def456", status="success")
        processor.gitlab_client.latest_pipeline_response = pipeline

        ctx = ProcessingContext(
            mr_iid=43,
            state_machine=sm,
            start_time=datetime.now(UTC),
            rebase_ctx=RebaseContext(old_sha="def456"),
        )

    with when("waiting for rebase to complete"):
        result = await processor._wait_for_rebase(ctx)

    with then("processing result is SUCCESS and rebase_complete is triggered with pipeline"):
        assert result == ProcessingResult.SUCCESS
        assert len(sm.rebase_complete_calls) == 1
        assert sm.rebase_complete_calls[0]["pipeline_id"] == 1002


__all__ = ["process_mr_with_async_rebase"]
