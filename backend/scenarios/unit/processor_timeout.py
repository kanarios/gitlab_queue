"""Test scenarios for processor timeout handling.

This scenario tests how the processor handles:
1. Rebase timeout
2. Pipeline timeout
3. Merge operation timeout
4. Label removed during pipeline wait (REMOVED)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from vedro import given, scenario, then, when

from gitlab_queue.core.polling import PollOutcome
from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import FakeCurrentState, create_mr
from scenarios.unit.processor._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


@scenario()
async def process_mr_with_rebase_timeout():
    """Rebase poll returns timed_out → ProcessingResult.TIMEOUT."""

    with given("processor with poll_fn that always times out"):

        async def timeout_poll(config, fn, shutdown_event, **kwargs):
            return PollOutcome(
                completed=False,
                timed_out=True,
                shutdown_requested=False,
                result=None,
            )

        processor = create_mock_processor(poll_fn=timeout_poll)
        sm = create_mock_state_machine()
        sm.current_state = FakeCurrentState(id="rebasing")
        ctx = create_processing_context(mr_iid=60, state_machine=sm)

    with when("processor waits for rebase that never completes"):
        result = await processor._wait_for_rebase(ctx)

    with then("result is TIMEOUT and state machine received timeout trigger"):
        assert result == ProcessingResult.TIMEOUT
        assert len(sm.timeout_calls) == 1


@scenario()
async def process_mr_with_pipeline_timeout():
    """Pipeline elapsed exceeds timeout → ProcessingResult.TIMEOUT."""

    with given("processor and context with expired timeout"):
        processor = create_mock_processor()
        sm = create_mock_state_machine()
        sm.current_state = FakeCurrentState(id="testing")
        ctx = create_processing_context(mr_iid=61, state_machine=sm)

        past_time = datetime.now(UTC) - timedelta(hours=1)
        timeout = timedelta(seconds=1)

    with when("processor checks pipeline termination with expired timeout"):
        result = await processor._check_pipeline_termination_conditions(
            ctx,
            sm,
            timeout=timeout,
            start_time=past_time,
        )

    with then("result is TIMEOUT and state machine received timeout trigger"):
        assert result == ProcessingResult.TIMEOUT
        assert len(sm.timeout_calls) == 1


@scenario()
async def process_mr_with_merge_timeout():
    """Merge operation raises TimeoutError → ProcessingResult.TIMEOUT."""

    with given("processor with wait_for_fn that raises TimeoutError"):

        async def timeout_wait_for(coro, timeout):
            # Must consume the coroutine to avoid RuntimeWarning
            coro.close()
            raise TimeoutError()

        processor = create_mock_processor(wait_for_fn=timeout_wait_for)
        sm = create_mock_state_machine()
        sm.current_state = FakeCurrentState(id="merging")
        ctx = create_processing_context(mr_iid=62, state_machine=sm)

        queue_item = create_test_queue_item(mr_iid=62, state="merging")
        processor.queue_manager.add_item(queue_item)

    with when("processor attempts merge that times out"):
        result = await processor._process_merge(ctx)

    with then("result is TIMEOUT and state machine received merge_failed trigger"):
        assert result == ProcessingResult.TIMEOUT
        assert len(sm.merge_failed_calls) == 1
        assert "timed out" in sm.merge_failed_calls[0]["error_message"].lower()


@scenario()
async def process_mr_with_label_removed_during_timeout():
    """Label removed during pipeline wait → ProcessingResult.REMOVED."""

    with given("MR without queue label and non-expired timeout"):
        mr_without_labels = create_mr(iid=63, labels=[], state="opened")
        processor = create_mock_processor()
        processor.gitlab_client.mr_responses[63] = mr_without_labels

        sm = create_mock_state_machine()
        sm.current_state = FakeCurrentState(id="testing")
        ctx = create_processing_context(mr_iid=63, state_machine=sm)

        start_time = datetime.now(UTC)
        timeout = timedelta(hours=1)

    with when("processor checks pipeline termination and MR has no label"):
        result = await processor._check_pipeline_termination_conditions(
            ctx,
            sm,
            timeout=timeout,
            start_time=start_time,
        )

    with then("result is REMOVED and state machine received mark_removed trigger"):
        assert result == ProcessingResult.REMOVED
        assert len(sm.mark_removed_calls) == 1
        assert sm.mark_removed_calls[0]["reason"] == "label_removed"


__all__ = [
    "process_mr_with_label_removed_during_timeout",
    "process_mr_with_merge_timeout",
    "process_mr_with_pipeline_timeout",
    "process_mr_with_rebase_timeout",
]
