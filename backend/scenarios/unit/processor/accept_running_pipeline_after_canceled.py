"""Test scenario: running pipeline with matching id and SHA is not skipped.

Verifies that _should_skip_stale_pipeline returns False when the queue item
has pipeline_id=1002 and expected_sha=abc123 matching the running pipeline.
"""

from __future__ import annotations

from vedro import given, scenario, then, when

from scenarios.unit.processor._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_test_queue_item,
)


@scenario()
async def accept_running_pipeline_after_canceled():
    with given("queue item matching the running pipeline"):
        processor = create_mock_processor()
        queue_item = create_test_queue_item(mr_iid=42, state="testing", pipeline_id=1002, expected_sha="abc123")
        processor.queue_manager.add_item(queue_item)
        pipeline = create_mock_pipeline(pipeline_id=1002, sha="abc123", status="running")

    with when("checking if stale"):
        result = await processor._should_skip_stale_pipeline(42, pipeline)

    with then("running pipeline is not skipped"):
        assert result is False


__all__ = ["accept_running_pipeline_after_canceled"]
