"""Test scenario: canceled pipeline is skipped when pipeline_id doesn't match.

Verifies that _should_skip_stale_pipeline returns True when the queue item
has pipeline_id=1002 but the incoming canceled pipeline has id=1001.
"""

from __future__ import annotations

from vedro import given, scenario, then, when

from scenarios.unit.processor._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_test_queue_item,
)


@scenario()
async def skip_canceled_pipeline_in_fast_forward():
    with given("queue item with pipeline_id=1002 and canceled pipeline with id=1001"):
        processor = create_mock_processor()
        queue_item = create_test_queue_item(mr_iid=42, state="testing", pipeline_id=1002, expected_sha="abc123")
        processor.queue_manager.add_item(queue_item)
        pipeline = create_mock_pipeline(pipeline_id=1001, sha="abc123", status="canceled")

    with when("checking if stale"):
        result = await processor._should_skip_stale_pipeline(42, pipeline)

    with then("canceled pipeline is skipped"):
        assert result is True


__all__ = ["skip_canceled_pipeline_in_fast_forward"]
