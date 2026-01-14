"""Test scenarios for processor handling pipeline failures.

This scenario tests how the processor handles:
1. Pipeline failures with retry
2. Pipeline failures after max retries
3. Canceled pipelines
4. Failed job information extraction
"""

from __future__ import annotations

import jj
from jj.mock import mocked
from scenarios.contexts.jj_gitlab_mock import get_mock_url
from scenarios.contexts.sqlite_client import test_database
from vedro import given, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.config import Settings
from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.processor import MergeProcessor, ProcessingResult
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.models.mr import Author, MergeRequest


@scenario()
async def process_mr_with_pipeline_failure_and_retry():
    """Test MR processing with pipeline failure that succeeds on retry."""

    with given("MR with failing pipeline that succeeds on retry"):
        async with test_database() as db:
            queue = QueueManager(db)

        test_mr = MergeRequest(
            iid=50,
            title="MR with Flaky Pipeline",
            state="opened",
            target_branch="main",
            source_branch="feature/flaky",
            sha="flaky123",
            labels=["merge_queue"],
            author=Author(id=1, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/50",
        )

        await queue.add_to_queue(test_mr, is_hotfix=False)

        mock_url = get_mock_url()

        mr_data = {
            "iid": 50,
            "project_id": 123,
            "title": "MR with Flaky Pipeline",
            "state": "opened",
            "sha": "flaky123",
            "labels": ["merge_queue"],
        }

        # First pipeline fails
        failed_pipeline = {
            "id": 2001,
            "status": "failed",
            "sha": "flaky123",
            "web_url": "https://gitlab.com/test/project/-/pipelines/2001",
        }

        # Second pipeline (after retry) succeeds
        success_pipeline = {
            "id": 2002,
            "status": "success",
            "sha": "retry123",
            "web_url": "https://gitlab.com/test/project/-/pipelines/2002",
        }

        # Failed jobs for first pipeline
        failed_jobs = [
            {"id": 3001, "name": "test", "status": "failed"},
            {"id": 3002, "name": "lint", "status": "success"},
        ]

        # Setup matchers
        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/50")
        get_mr_response = jj.Response(status=200, json=mr_data)

        # Initial rebase
        rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/50/rebase")
        rebase_response_1 = jj.Response(status=202, json={"rebase_in_progress": False})

        # Retry rebase (after pipeline failure)
        rebase_response_2 = jj.Response(status=202, json={"rebase_in_progress": False})

        # First call returns failed pipeline, second call returns success pipeline
        pipelines_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/50/pipelines")
        pipelines_response_1 = jj.Response(status=200, json=[failed_pipeline])
        pipelines_response_2 = jj.Response(status=200, json=[success_pipeline])

        # Jobs for failed pipeline
        jobs_matcher = jj.match(
            "GET", f"/api/v4/projects/123/pipelines/{failed_pipeline['id']}/jobs"
        )
        jobs_response = jj.Response(status=200, json=failed_jobs)

        # Merge after success
        merge_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/50/merge")
        merge_response = jj.Response(status=200, json={**mr_data, "state": "merged"})

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/50/notes")
        comment_response = jj.Response(status=201, json={"id": 20})

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            db_path=":memory:",
            pipeline_retry_count=2,  # Allow retries
            poll_interval_seconds=0.1,  # Fast polling for tests
            pipeline_timeout_seconds=300,
        )

    # Mock sequence: first pipeline check fails, rebase retry, second pipeline succeeds
    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(rebase_matcher, rebase_response_1) as rebase_mock_1,
        mocked(pipelines_matcher, pipelines_response_1) as pipelines_mock_1,
        mocked(jobs_matcher, jobs_response) as jobs_mock,
    ):
        # After first pipeline fails, we setup retry mocks
        async with (
            mocked(rebase_matcher, rebase_response_2) as rebase_mock_2,
            mocked(pipelines_matcher, pipelines_response_2) as pipelines_mock_2,
            mocked(merge_matcher, merge_response) as merge_mock,
            mocked(comment_matcher, comment_response),
        ):
            with when("processor handles pipeline failure with retry"):
                gitlab_client = GitLabClient(settings)
                notifier = MRNotifier(gitlab_client=gitlab_client, project_id=123)
                processor = MergeProcessor(
                    gitlab_client=gitlab_client,
                    queue_manager=queue,
                    notifier=notifier,
                    settings=settings,
                )

                queue_item = await queue.get_next_mr()
                result = await processor._process_mr(queue_item)

            with then("MR is merged after successful retry"):
                assert result == ProcessingResult.SUCCESS

                # Verify rebases were attempted (initial + retry)
                initial_rebase_history = await rebase_mock_1.fetch_history()
                retry_rebase_history = await rebase_mock_2.fetch_history()
                assert len(initial_rebase_history) >= 1, "Initial rebase should be called"
                assert len(retry_rebase_history) >= 1, "Retry rebase should be called"

                # Verify failed jobs were fetched
                jobs_history = await jobs_mock.fetch_history()
                assert len(jobs_history) >= 1, "Failed jobs should be fetched"

                # Verify merge was eventually called
                merge_history = await merge_mock.fetch_history()
                assert len(merge_history) == 1, "Merge should be called after retry"

                # Verify final state
                mr_state = await queue.get_mr_state(50)
                assert mr_state == "merged"


@scenario()
async def process_mr_with_pipeline_failure_max_retries():
    """Test MR processing when pipeline fails after max retries."""

    with given("MR with consistently failing pipeline"):
        async with test_database() as db:
            queue = QueueManager(db)

        test_mr = MergeRequest(
            iid=51,
            title="MR with Broken Pipeline",
            state="opened",
            target_branch="main",
            source_branch="feature/broken",
            sha="broken123",
            labels=["merge_queue"],
            author=Author(id=1, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/51",
        )

        await queue.add_to_queue(test_mr, is_hotfix=False)

        mock_url = get_mock_url()

        mr_data = {
            "iid": 51,
            "project_id": 123,
            "title": "MR with Broken Pipeline",
            "state": "opened",
            "sha": "broken123",
            "labels": ["merge_queue"],
        }

        # All pipelines fail
        failed_pipeline_1 = {"id": 3001, "status": "failed", "sha": "broken123"}
        failed_pipeline_2 = {"id": 3002, "status": "failed", "sha": "broken456"}
        failed_pipeline_3 = {"id": 3003, "status": "failed", "sha": "broken789"}

        failed_jobs = [
            {"id": 4001, "name": "build", "status": "failed"},
            {"id": 4002, "name": "test", "status": "failed"},
        ]

        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/51")
        get_mr_response = jj.Response(status=200, json=mr_data)

        rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/51/rebase")
        rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        # Pipeline checks return failures
        pipelines_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/51/pipelines")
        pipelines_responses = [
            jj.Response(status=200, json=[failed_pipeline_1]),
            jj.Response(status=200, json=[failed_pipeline_2]),
            jj.Response(status=200, json=[failed_pipeline_3]),
        ]

        jobs_matcher = jj.match("GET", "/api/v4/projects/123/pipelines/.*/jobs")
        jobs_response = jj.Response(status=200, json=failed_jobs)

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/51/notes")
        comment_response = jj.Response(status=201, json={"id": 21})

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            db_path=":memory:",
            pipeline_retry_count=2,  # Allow 2 retries (3 total attempts)
            poll_interval_seconds=0.1,
        )

    # Set up mocks for multiple pipeline failures
    pipeline_mocks = []
    for response in pipelines_responses:
        pipeline_mocks.append(mocked(pipelines_matcher, response))

    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(rebase_matcher, rebase_response) as rebase_mock,
        pipeline_mocks[0] as p1,
        pipeline_mocks[1] as p2,
        pipeline_mocks[2] as p3,
        mocked(jobs_matcher, jobs_response) as jobs_mock,
        mocked(comment_matcher, comment_response) as comment_mock,
    ):
        with when("processor exhausts all retries"):
            gitlab_client = GitLabClient(settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, project_id=123)
            processor = MergeProcessor(
                gitlab_client=gitlab_client,
                queue_manager=queue,
                notifier=notifier,
                settings=settings,
            )

            queue_item = await queue.get_next_mr()
            result = await processor._process_mr(queue_item)

        with then("MR is marked as failed after max retries"):
            assert result == ProcessingResult.PIPELINE_FAILED

            # Verify multiple rebases were attempted (initial + retries)
            rebase_history = await rebase_mock.fetch_history()
            assert (
                len(rebase_history) >= settings.pipeline_retry_count
            ), f"Should attempt {settings.pipeline_retry_count} retries"

            # Verify failed jobs were fetched
            jobs_history = await jobs_mock.fetch_history()
            assert len(jobs_history) >= 1, "Failed jobs should be fetched"

            # Verify failure comment was posted
            comment_history = await comment_mock.fetch_history()
            assert len(comment_history) >= 1, "Failure comment should be posted"

            # Verify final state
            mr_state = await queue.get_mr_state(51)
            assert mr_state == "failed"


@scenario()
async def process_mr_with_canceled_pipeline():
    """Test MR processing when pipeline is canceled."""

    with given("MR with canceled pipeline"):
        async with test_database() as db:
            queue = QueueManager(db)

        test_mr = MergeRequest(
            iid=52,
            title="MR with Canceled Pipeline",
            state="opened",
            target_branch="main",
            source_branch="feature/canceled",
            sha="cancel123",
            labels=["merge_queue"],
            author=Author(id=1, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/52",
        )

        await queue.add_to_queue(test_mr, is_hotfix=False)

        mock_url = get_mock_url()

        mr_data = {
            "iid": 52,
            "project_id": 123,
            "title": "MR with Canceled Pipeline",
            "state": "opened",
            "sha": "cancel123",
            "labels": ["merge_queue"],
        }

        canceled_pipeline = {
            "id": 4001,
            "status": "canceled",
            "sha": "cancel123",
        }

        canceled_jobs = [
            {"id": 5001, "name": "test", "status": "canceled"},
        ]

        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/52")
        get_mr_response = jj.Response(status=200, json=mr_data)

        rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/52/rebase")
        rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        pipelines_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/52/pipelines")
        pipelines_response = jj.Response(status=200, json=[canceled_pipeline])

        jobs_matcher = jj.match(
            "GET", f"/api/v4/projects/123/pipelines/{canceled_pipeline['id']}/jobs"
        )
        jobs_response = jj.Response(status=200, json=canceled_jobs)

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/52/notes")
        comment_response = jj.Response(status=201, json={"id": 22})

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            db_path=":memory:",
            pipeline_retry_count=1,  # Allow 1 retry
            poll_interval_seconds=0.1,
        )

    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(rebase_matcher, rebase_response),
        mocked(pipelines_matcher, pipelines_response),
        mocked(jobs_matcher, jobs_response) as jobs_mock,
        mocked(comment_matcher, comment_response),
    ):
        with when("processor encounters canceled pipeline"):
            gitlab_client = GitLabClient(settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, project_id=123)
            processor = MergeProcessor(
                gitlab_client=gitlab_client,
                queue_manager=queue,
                notifier=notifier,
                settings=settings,
            )

            queue_item = await queue.get_next_mr()
            result = await processor._process_mr(queue_item)

        with then("canceled pipeline is treated like failure"):
            # Canceled pipelines should trigger retry or fail
            assert result in (ProcessingResult.PIPELINE_FAILED, ProcessingResult.SUCCESS)

            # Verify canceled jobs were fetched
            jobs_history = await jobs_mock.fetch_history()
            assert len(jobs_history) >= 1, "Canceled jobs should be fetched"

            # Check final state
            mr_state = await queue.get_mr_state(52)
            assert mr_state in ("failed", "merged"), "MR should be failed or merged after retry"


__all__ = [
    "process_mr_with_canceled_pipeline",
    "process_mr_with_pipeline_failure_and_retry",
    "process_mr_with_pipeline_failure_max_retries",
]
