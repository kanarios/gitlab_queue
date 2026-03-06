"""Test scenarios for processor handling pipeline failures.

This scenario tests how the processor handles:
1. Pipeline failure retry that succeeds (rebase + new pipeline)
2. Pipeline failure after max retries exhausted
3. Canceled pipeline treated as failure
"""

from __future__ import annotations

from vedro import given, scenario, then, when

from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import FakeGitLabClient, create_job, create_mr, create_pipeline
from scenarios.unit.processor._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
    instant_poll,
)


@scenario()
async def process_mr_with_pipeline_failure_and_retry():
    """Pipeline failure triggers rebase + new pipeline via _handle_pipeline_failure_retry."""

    with given("processor with FakeGitLabClient configured for successful retry"):
        mr_before_rebase = create_mr(iid=42, sha="sha_old", source_branch="feature/flaky")
        mr_after_rebase = create_mr(iid=42, sha="sha_new", source_branch="feature/flaky")

        new_pipeline = create_pipeline(id=200, sha="sha_new", status="running")

        gitlab_client = FakeGitLabClient(
            rebase_status=(False, False),
            mr_response_sequence=[mr_before_rebase, mr_after_rebase],
            latest_pipeline_response=new_pipeline,
        )

        processor = create_mock_processor(
            gitlab_client=gitlab_client,
            poll_fn=instant_poll,
        )

        queue_item = create_test_queue_item(mr_iid=42, state="testing", expected_sha="sha_old")
        processor.queue_manager.add_item(queue_item)

        sm = create_mock_state_machine()
        ctx = create_processing_context(mr_iid=42, state_machine=sm)

        old_pipeline = create_mock_pipeline(pipeline_id=100, sha="sha_old", status="failed")

    with when("_handle_pipeline_failure_retry is called with retries remaining"):
        should_continue, new_start_time = await processor._handle_pipeline_failure_retry(
            ctx,
            pipeline=old_pipeline,
            failed_jobs=["test"],
            retry_count=0,
            max_retries=2,
        )

    with then("retry succeeds and signals to continue with new start time"):
        assert should_continue is True
        assert new_start_time is not None
        assert len(sm.pipeline_retry_calls) == 1
        assert sm.pipeline_retry_calls[0]["old_pipeline_id"] == 100
        assert sm.pipeline_retry_calls[0]["new_pipeline_id"] == 200
        assert sm.pipeline_retry_calls[0]["retry_count"] == 1
        assert sm.pipeline_retry_calls[0]["expected_sha"] == "sha_new"
        assert len(gitlab_client.rebase_calls) == 1


@scenario()
async def process_mr_with_pipeline_failure_max_retries():
    """Pipeline failure with max retries exhausted triggers pipeline_failed."""

    with given("processor and state machine for max-retries-exceeded case"):
        processor = create_mock_processor()

        sm = create_mock_state_machine()
        ctx = create_processing_context(mr_iid=42, state_machine=sm)

        pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

    with when("_handle_pipeline_failure_retry is called at max retries"):
        should_continue, new_start_time = await processor._handle_pipeline_failure_retry(
            ctx,
            pipeline=pipeline,
            failed_jobs=["build"],
            retry_count=2,
            max_retries=2,
        )

    with then("retry is not attempted and pipeline_failed is triggered"):
        assert should_continue is False
        assert new_start_time is None
        assert len(sm.pipeline_failed_calls) == 1
        assert sm.pipeline_failed_calls[0]["failed_jobs"] == ["build"]
        assert sm.pipeline_failed_calls[0]["retry_count"] == 2
        assert sm.pipeline_failed_calls[0]["error_message"] == "Pipeline failed"


@scenario()
async def process_mr_with_canceled_pipeline():
    """Canceled pipeline is treated as failure via _handle_pipeline_status."""

    with given("processor with canceled pipeline and no retries left"):
        gitlab_client = FakeGitLabClient(
            pipeline_jobs_response=[create_job(name="deploy", status="canceled")],
        )
        processor = create_mock_processor(gitlab_client=gitlab_client)

        queue_item = create_test_queue_item(mr_iid=42, state="testing", retry_count=1)
        processor.queue_manager.add_item(queue_item)

        sm = create_mock_state_machine()
        ctx = create_processing_context(mr_iid=42, state_machine=sm)

        pipeline = create_mock_pipeline(pipeline_id=300, sha="abc123", status="canceled")

    with when("_handle_pipeline_status is called with canceled pipeline"):
        result = await processor._handle_pipeline_status(
            ctx,
            sm,
            pipeline,
            retry_count=1,
            max_retries=1,
        )

    with then("result is PIPELINE_FAILED"):
        assert result == ProcessingResult.PIPELINE_FAILED
        assert len(sm.pipeline_failed_calls) == 1
        assert sm.pipeline_failed_calls[0]["failed_jobs"] == ["deploy"]


__all__ = [
    "process_mr_with_canceled_pipeline",
    "process_mr_with_pipeline_failure_and_retry",
    "process_mr_with_pipeline_failure_max_retries",
]
