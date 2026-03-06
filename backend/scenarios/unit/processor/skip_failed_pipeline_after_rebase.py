"""Test scenario: failed pipeline with wrong SHA is skipped.

Verifies that _should_skip_stale_pipeline returns True when the queue item
has expected_sha=new_sha_456 but the incoming failed pipeline has sha=old_sha_123.
"""

from __future__ import annotations

from vedro import given, scenario, then, when

from scenarios.unit.processor._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_test_queue_item,
)


@scenario()
async def skip_failed_pipeline_after_rebase():
    with given("queue item with expected_sha=new_sha and failed pipeline with old sha"):
        processor = create_mock_processor()
        queue_item = create_test_queue_item(mr_iid=42, state="testing", expected_sha="new_sha_456")
        processor.queue_manager.add_item(queue_item)
        pipeline = create_mock_pipeline(pipeline_id=1001, sha="old_sha_123", status="failed")

    with when("checking if stale"):
        result = await processor._should_skip_stale_pipeline(42, pipeline)

    with then("failed pipeline is skipped due to SHA mismatch"):
        assert result is True


__all__ = ["skip_failed_pipeline_after_rebase"]
