"""Test scenarios for processor handling pipeline failures.

This scenario tests how the processor handles:
1. Pipeline failure with job retry that succeeds
2. Pipeline failure after job retries exhausted
3. Canceled pipeline treated as failure
"""

from __future__ import annotations

from vedro import given, scenario, then, when

from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import FakeGitLabClient, FakeSettings, create_job
from scenarios.unit.processor._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


@scenario()
async def process_mr_with_pipeline_failure_and_retry():
    """Pipeline failure triggers job retry via handle_pipeline_failure_retry."""

    with given("processor with FakeGitLabClient configured for job retry"):
        failed_job = create_job(id=1, name="test", status="failed")

        gitlab_client = FakeGitLabClient(
            pipeline_jobs_response=[failed_job],
        )

        processor = create_mock_processor(
            gitlab_client=gitlab_client,
            settings=FakeSettings(job_retry_count=2),
        )

        queue_item = create_test_queue_item(mr_iid=42, state="testing", expected_sha="sha_old")
        processor.queue_manager.add_item(queue_item)

        sm = create_mock_state_machine()
        ctx = create_processing_context(mr_iid=42, state_machine=sm)

        old_pipeline = create_mock_pipeline(pipeline_id=100, sha="sha_old", status="failed")

    with when("_handle_pipeline_failure_retry is called with retries remaining"):
        should_continue, new_start_time, updated_retried = await processor._handle_pipeline_failure_retry(
            ctx,
            pipeline=old_pipeline,
            retried_jobs={},
        )

    with then("retry succeeds and signals to continue with new start time"):
        assert should_continue is True
        assert new_start_time is not None
        assert updated_retried["test"] == 1
        assert len(gitlab_client.retry_job_calls) == 1


@scenario()
async def process_mr_with_pipeline_failure_max_retries():
    """Pipeline failure with job retries exhausted triggers pipeline_failed."""

    with given("processor and state machine for max-retries-exceeded case"):
        failed_job = create_job(id=1, name="build", status="failed")

        gitlab_client = FakeGitLabClient(
            pipeline_jobs_response=[failed_job],
        )
        processor = create_mock_processor(
            gitlab_client=gitlab_client,
            settings=FakeSettings(job_retry_count=1),
        )

        sm = create_mock_state_machine()
        ctx = create_processing_context(mr_iid=42, state_machine=sm)

        pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

    with when("_handle_pipeline_failure_retry is called at max retries"):
        should_continue, new_start_time, _updated_retried = await processor._handle_pipeline_failure_retry(
            ctx,
            pipeline=pipeline,
            retried_jobs={"build": 1},
        )

    with then("retry is not attempted and pipeline_failed is triggered"):
        assert should_continue is False
        assert new_start_time is None
        assert len(sm.pipeline_failed_calls) == 1
        assert sm.pipeline_failed_calls[0]["failed_jobs"] == ["build"]


@scenario()
async def process_mr_with_canceled_pipeline():
    """Canceled pipeline is treated as failure via _handle_pipeline_status."""

    with given("processor with canceled pipeline and no retries left"):
        gitlab_client = FakeGitLabClient(
            pipeline_jobs_response=[create_job(name="deploy", status="canceled")],
        )
        processor = create_mock_processor(
            gitlab_client=gitlab_client,
            settings=FakeSettings(job_retry_count=1),
        )

        queue_item = create_test_queue_item(mr_iid=42, state="testing")
        processor.queue_manager.add_item(queue_item)

        sm = create_mock_state_machine()
        ctx = create_processing_context(mr_iid=42, state_machine=sm)

        pipeline = create_mock_pipeline(pipeline_id=300, sha="abc123", status="canceled")

    with when("_handle_pipeline_status is called with canceled pipeline"):
        result = await processor._handle_pipeline_status(
            ctx,
            sm,
            pipeline,
            retried_jobs={},
        )

    with then("result is PIPELINE_FAILED"):
        assert result == ProcessingResult.PIPELINE_FAILED
        assert len(sm.pipeline_failed_calls) == 1


__all__ = [
    "process_mr_with_canceled_pipeline",
    "process_mr_with_pipeline_failure_and_retry",
    "process_mr_with_pipeline_failure_max_retries",
]
