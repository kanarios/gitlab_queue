from __future__ import annotations

from vedro import given, params, scenario, then, when

from gitlab_queue.core.processor import ProcessingResult
from scenarios.unit.processor._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


@scenario(
    [
        params("manual"),
        params("skipped"),
        params("blocked"),
        params("waiting_for_resource"),
    ]
)
async def process_mr_with_non_actionable_pipeline_status(status: str):
    with given(f"a processor and pipeline in '{status}' status"):
        sm = create_mock_state_machine()
        processor = create_mock_processor()
        item = create_test_queue_item(mr_iid=42, state="testing")
        processor.queue_manager.add_item(item)
        ctx = create_processing_context(mr_iid=42, state_machine=sm)
        pipeline = create_mock_pipeline(pipeline_id=9001, sha="abc123", status=status)

    with when("processor handles the pipeline status"):
        result = await processor._handle_pipeline_status(ctx, sm, pipeline, retried_jobs={})

    with then("result is PIPELINE_FAILED"):
        assert result == ProcessingResult.PIPELINE_FAILED

    with then("state machine received pipeline_failed trigger"):
        assert len(sm.pipeline_failed_calls) == 1

    with then("error message contains the status name"):
        assert status in sm.pipeline_failed_calls[0]["error_message"]


@scenario()
async def non_actionable_status_does_not_retry():
    with given("a processor and pipeline in 'manual' status"):
        sm = create_mock_state_machine()
        processor = create_mock_processor()
        item = create_test_queue_item(mr_iid=42, state="testing")
        processor.queue_manager.add_item(item)
        ctx = create_processing_context(mr_iid=42, state_machine=sm)
        pipeline = create_mock_pipeline(pipeline_id=9002, sha="abc123", status="manual")

    with when("processor handles the pipeline status"):
        result = await processor._handle_pipeline_status(ctx, sm, pipeline, retried_jobs={})

    with then("result is PIPELINE_FAILED"):
        assert result == ProcessingResult.PIPELINE_FAILED

    with then("no rebase was attempted"):
        assert processor.gitlab_client.rebase_calls == []


__all__ = [
    "non_actionable_status_does_not_retry",
    "process_mr_with_non_actionable_pipeline_status",
]
