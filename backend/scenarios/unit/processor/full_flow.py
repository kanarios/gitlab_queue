"""Unit test scenarios for processor sub-flows.

Tests processor methods (_process_rebase, _handle_pipeline_failure_retry)
using Fakes instead of real DB + transport.
"""

from __future__ import annotations

from vedro import given, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabConflictError
from gitlab_queue.core.processor import ProcessingResult
from scenarios.unit.processor._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    instant_poll,
)


@scenario()
async def flaky_pipeline_retry_succeeds_in_flow():
    """Test pipeline failure retry continues processing when retries available."""

    with given("processor with a failed pipeline and retries available"):
        processor = create_mock_processor(poll_fn=instant_poll)
        processor.gitlab_client.rebase_status = (False, False)

        sm = create_mock_state_machine()
        ctx = create_processing_context(mr_iid=400, state_machine=sm)

        old_pipeline = create_mock_pipeline(
            pipeline_id=8000,
            sha="flaky123",
            status="failed",
        )

    with when("pipeline failure retry is attempted with retries remaining"):
        should_continue, new_start = await processor._handle_pipeline_failure_retry(
            ctx,
            old_pipeline,
            failed_jobs=["test"],
            retry_count=0,
            max_retries=2,
        )

    with then("retry continues and state machine is notified"):
        assert should_continue is True
        assert new_start is not None
        assert len(sm.pipeline_retry_calls) == 1


@scenario()
async def conflict_detected_in_flow():
    """Test rebase conflict is detected and reported via state machine."""

    with given("processor whose gitlab client raises conflict on rebase"):
        processor = create_mock_processor()
        processor.gitlab_client.rebase_mr_error = GitLabConflictError("Conflict")

        sm = create_mock_state_machine()
        ctx = create_processing_context(mr_iid=402, state_machine=sm)

    with when("rebase is attempted"):
        result = await processor._process_rebase(ctx)

    with then("conflict result is returned and state machine records failure"):
        assert result == ProcessingResult.CONFLICT
        assert len(sm.rebase_failed_calls) == 1


__all__ = [
    "conflict_detected_in_flow",
    "flaky_pipeline_retry_succeeds_in_flow",
]
