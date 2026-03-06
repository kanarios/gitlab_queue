"""Test scenarios for processor graceful shutdown.

This scenario tests how the processor handles:
1. Shutdown with no active processing
2. Shutdown during rebase (poll_fn returns shutdown_requested)
3. State recovery after shutdown resets intermediate states
4. Shutdown timeout handling
5. Shutdown flag detected during pipeline wait
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from vedro import given, scenario, then, when

from gitlab_queue.core.polling import PollOutcome
from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import create_mr
from scenarios.unit.processor._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


@scenario()
async def graceful_shutdown_with_no_processing():
    """Test graceful shutdown when no MR is being processed."""

    with given("processor with empty queue"):
        processor = create_mock_processor()

    with when("shutdown is requested"):
        processor.request_shutdown()

    with then("processor reports shutdown state cleanly"):
        assert processor.is_shutdown_requested is True
        assert processor.is_processing is False
        assert processor.current_mr_iid is None


@scenario()
async def graceful_shutdown_during_rebase():
    """Test that shutdown during rebase returns ERROR via poll_fn."""

    with given("processor with poll_fn that signals shutdown"):

        async def shutdown_poll(config, fn, shutdown_event, **kwargs):
            return PollOutcome(
                completed=False,
                timed_out=False,
                shutdown_requested=True,
                result=None,
            )

        processor = create_mock_processor(poll_fn=shutdown_poll)

        mr = create_mr(iid=70, state="opened", labels=["merge_queue"])
        processor.gitlab_client.mr_responses[70] = mr

    with when("_wait_for_rebase is called with shutdown signaled"):
        ctx = create_processing_context(mr_iid=70)
        result = await processor._wait_for_rebase(ctx)

    with then("processing result is ERROR"):
        assert result == ProcessingResult.ERROR


@scenario()
async def processor_state_recovery_after_shutdown():
    """Test that _recover_interrupted_state resets intermediate states to queued."""

    with given("MRs in various states after a shutdown"):
        processor = create_mock_processor()

        states = [
            (71, "queued"),
            (72, "rebasing"),
            (73, "testing"),
            (74, "merging"),
        ]

        for mr_iid, state in states:
            item = create_test_queue_item(mr_iid=mr_iid, state=state)
            processor.queue_manager.add_item(item)
            processor.gitlab_client.mr_responses[mr_iid] = create_mr(
                iid=mr_iid,
                state="opened",
                labels=["merge_queue"],
            )

    with when("processor runs state recovery"):
        await processor._recover_interrupted_state()

    with then("all intermediate states are reset to queued"):
        for mr_iid in [71, 72, 73, 74]:
            item = await processor.queue_manager.get_queue_item(mr_iid)
            assert item is not None, f"MR {mr_iid} should still be in the queue"
            assert item.state == "queued", f"MR {mr_iid} should be 'queued', got '{item.state}'"


@scenario()
async def shutdown_timeout_handling():
    """Test that shutdown request sets the flag even with a short timeout."""

    with given("processor running"):
        processor = create_mock_processor()

    with when("shutdown is requested and waited with a short timeout"):
        processor.request_shutdown()
        shutdown_complete = await processor.wait_for_shutdown(timeout=0.001)

    with then("shutdown flag is set and wait completed"):
        assert processor.is_shutdown_requested is True
        assert shutdown_complete is True


@scenario()
async def concurrent_processing_during_shutdown():
    """Test that shutdown event is detected during pipeline termination checks."""

    with given("processor with shutdown event already set"):
        processor = create_mock_processor()
        processor._shutdown_event.set()

        sm = create_mock_state_machine()
        ctx = create_processing_context(mr_iid=75, state_machine=sm)

    with when("pipeline termination conditions are checked"):
        result = await processor._check_pipeline_termination_conditions(
            ctx,
            sm,
            timeout=timedelta(hours=1),
            start_time=datetime.now(UTC),
        )

    with then("result is ERROR due to shutdown"):
        assert result == ProcessingResult.ERROR


__all__ = [
    "concurrent_processing_during_shutdown",
    "graceful_shutdown_during_rebase",
    "graceful_shutdown_with_no_processing",
    "processor_state_recovery_after_shutdown",
    "shutdown_timeout_handling",
]
