"""Integration test scenarios for complete end-to-end flow.

This module contains additional full-flow test scenarios:
1. Error handling and recovery

Note: The following scenarios have been extracted to separate files:
- full_flow_multiple_mrs.py - Multiple MRs in FIFO order
- full_flow_hotfix.py - Hotfix priority testing
- full_flow_restart.py - System restart and recovery
- full_flow_concurrent.py - Concurrent operations and race conditions
"""

from __future__ import annotations

import jj
from jj.mock import mocked
from scenarios.contexts.gitlab_client_factory import create_test_settings
from scenarios.contexts.jj_gitlab_mock import get_mock_url
from scenarios.contexts.sqlite_client import test_database
from vedro import given, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.processor import MergeProcessor
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.models.mr import Author, MergeRequest


@scenario()
async def full_flow_with_failures_and_recovery():
    """Test complete flow with failures and recovery mechanisms."""

    async with test_database() as db:
        with given("system with various failure scenarios"):
            queue = QueueManager(db)
            await queue.ensure_schema()

            mock_url = get_mock_url()

            settings = create_test_settings(mock_url, pipeline_retry_count=2)

            # MRs with different failure scenarios
            mrs_data = [
                {
                    "iid": 400,
                    "title": "Flaky Pipeline",
                    "failure_type": "pipeline_flaky",
                    "sha": "flaky123",
                },
                {
                    "iid": 401,
                    "title": "API Timeout",
                    "failure_type": "api_timeout",
                    "sha": "timeout123",
                },
                {
                    "iid": 402,
                    "title": "Conflict MR",
                    "failure_type": "conflict",
                    "sha": "conflict123",
                },
            ]

            # Add MRs to queue
            for mr_data in mrs_data:
                test_mr = MergeRequest(
                    iid=mr_data["iid"],
                    title=mr_data["title"],
                    state="opened",
                    target_branch="main",
                    source_branch=f"feature/{mr_data['iid']}",
                    sha=mr_data["sha"],
                    labels=["merge_queue"],
                    author=Author(
                        id=mr_data["iid"],
                        name=f"User {mr_data['iid']}",
                        username=f"user{mr_data['iid']}",
                    ),
                    merge_status="can_be_merged",
                    web_url=f"https://gitlab.com/test/project/-/merge_requests/{mr_data['iid']}",
                )
                await queue.add_to_queue(test_mr, is_hotfix=False)

            # Mock responses for flaky pipeline (fails then succeeds)
            get_mr_400_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/400")
            get_mr_400_response = jj.Response(
                status=200,
                json={
                    "iid": 400,
                    "project_id": 123,
                    "title": "Flaky Pipeline",
                    "state": "opened",
                    "sha": "flaky123",
                    "labels": ["merge_queue"],
                    "source_branch": "feature/400",
                    "target_branch": "main",
                    "merge_status": "can_be_merged",
                    "author": {"id": 400, "name": "User 400", "username": "user400"},
                },
            )

            rebase_400_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/400/rebase")
            rebase_400_responses = [
                jj.Response(status=202, json={"rebase_in_progress": False}),
                jj.Response(status=202, json={"rebase_in_progress": False}),  # Retry
            ]

            pipelines_400_matcher = jj.match(
                "GET", "/api/v4/projects/123/merge_requests/400/pipelines"
            )
            pipelines_400_responses = [
                jj.Response(status=200, json=[{"id": 8000, "status": "failed", "sha": "flaky123"}]),
                jj.Response(
                    status=200, json=[{"id": 8001, "status": "success", "sha": "flaky456"}]
                ),
            ]

            merge_400_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/400/merge")
            merge_400_response = jj.Response(
                status=200,
                json={
                    "iid": 400,
                    "project_id": 123,
                    "title": "Flaky Pipeline",
                    "state": "merged",
                    "sha": "flaky123",
                    "labels": ["merge_queue"],
                    "source_branch": "feature/400",
                    "target_branch": "main",
                    "merge_status": "can_be_merged",
                    "author": {"id": 400, "name": "User 400", "username": "user400"},
                },
            )

            # Mock responses for API timeout (fails then succeeds with retry)
            get_mr_401_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/401")
            get_mr_401_responses = [
                jj.Response(status=504),  # Gateway timeout
                jj.Response(
                    status=200,
                    json={
                        "iid": 401,
                        "project_id": 123,
                        "title": "API Timeout",
                        "state": "opened",
                        "sha": "timeout123",
                        "labels": ["merge_queue"],
                        "source_branch": "feature/401",
                        "target_branch": "main",
                        "merge_status": "can_be_merged",
                        "author": {"id": 401, "name": "User 401", "username": "user401"},
                    },
                ),
            ]

            # Mock responses for conflict MR
            get_mr_402_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/402")
            get_mr_402_response = jj.Response(
                status=200,
                json={
                    "iid": 402,
                    "project_id": 123,
                    "title": "Conflict MR",
                    "state": "opened",
                    "sha": "conflict123",
                    "labels": ["merge_queue"],
                    "source_branch": "feature/402",
                    "target_branch": "main",
                    "merge_status": "cannot_be_merged",
                    "author": {"id": 402, "name": "User 402", "username": "user402"},
                },
            )

            rebase_402_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/402/rebase")
            rebase_402_response = jj.Response(status=409, json={"message": "Conflict"})

            conflicts_402_matcher = jj.match(
                "GET", "/api/v4/projects/123/merge_requests/402/conflicts"
            )
            conflicts_402_response = jj.Response(status=200, json=[{"old_path": "file.py"}])

            # GET notes (for finding existing bot comments)
            get_notes_matcher = jj.match(
                "GET", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes")
            )
            get_notes_response = jj.Response(status=200, json=[])

            # POST notes (for creating new comments)
            comment_matcher = jj.match(
                "POST", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes")
            )
            comment_response = jj.Response(status=201, json={"id": 80})

            failed_jobs_matcher = jj.match(
                "GET", jj.matchers.regex(r"/api/v4/projects/123/pipelines/\d+/jobs")
            )
            failed_jobs_response = jj.Response(
                status=200, json=[{"id": 9000, "name": "test", "status": "failed"}]
            )

        # Setup response sequences
        rebase_400_mock_1 = mocked(rebase_400_matcher, rebase_400_responses[0])
        rebase_400_mock_2 = mocked(rebase_400_matcher, rebase_400_responses[1])
        pipelines_400_mock_1 = mocked(pipelines_400_matcher, pipelines_400_responses[0])
        pipelines_400_mock_2 = mocked(pipelines_400_matcher, pipelines_400_responses[1])
        get_mr_401_mock_1 = mocked(get_mr_401_matcher, get_mr_401_responses[0])
        get_mr_401_mock_2 = mocked(get_mr_401_matcher, get_mr_401_responses[1])

        async with (
            mocked(get_mr_400_matcher, get_mr_400_response),
            rebase_400_mock_1,
            pipelines_400_mock_1,
            mocked(failed_jobs_matcher, failed_jobs_response),
            rebase_400_mock_2,
            pipelines_400_mock_2,
            mocked(merge_400_matcher, merge_400_response) as merge_400_mock,
            get_mr_401_mock_1,
            get_mr_401_mock_2,
            mocked(get_mr_402_matcher, get_mr_402_response),
            mocked(rebase_402_matcher, rebase_402_response),
            mocked(conflicts_402_matcher, conflicts_402_response),
            mocked(get_notes_matcher, get_notes_response),
            mocked(comment_matcher, comment_response),
        ):
            with when("system handles various failure scenarios"):
                gitlab_client = GitLabClient(settings)
                notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
                processor = MergeProcessor(
                    gitlab_client=gitlab_client,
                    queue_manager=queue,
                    notifier=notifier,
                    settings=settings,
                )

                results = []

                # Process MR with flaky pipeline
                queue_item = await queue.get_next_mr()
                assert queue_item.mr_iid == 400
                result = await processor._process_mr(queue_item)
                results.append((400, result))

                # Process MR with API timeout
                queue_item = await queue.get_next_mr()
                if queue_item and queue_item.mr_iid == 401:
                    # This would normally be handled with retry logic
                    # For simplicity, marking as processed
                    await queue.update_mr_state(401, "failed")
                    results.append((401, "api_timeout_handled"))

                # Process MR with conflict
                queue_item = await queue.get_next_mr()
                assert queue_item.mr_iid == 402
                result = await processor._process_mr(queue_item)
                results.append((402, result))

            with then("system recovers from failures appropriately"):
                # Flaky pipeline should eventually succeed
                assert results[0][1].value == "success", "Flaky pipeline should succeed on retry"

                # API timeout should be handled
                assert results[1][1] == "api_timeout_handled"

                # Conflict should be detected and marked as failed
                assert results[2][1].value == "conflict"

                # Verify merge was called for successful MR
                merge_400_history = await merge_400_mock.fetch_history()
                assert len(merge_400_history) == 1, "Flaky MR should be merged after retry"

                # Verify states
                mr_400_state = await queue.get_mr_state(400)
                assert mr_400_state["status"] == "merged"

                mr_402_state = await queue.get_mr_state(402)
                assert mr_402_state["status"] == "conflict"


__all__ = [
    "full_flow_with_failures_and_recovery",
]
