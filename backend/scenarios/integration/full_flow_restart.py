"""Integration test scenario for system restart and state recovery.

This scenario tests:
1. MRs in various intermediate states (queued, rebasing, testing, merging)
2. System shutdown and restart
3. State recovery and continuation of processing
"""

from __future__ import annotations

import jj
from jj.mock import mocked
from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.contexts.jj_gitlab_mock import get_mock_url
from scenarios.contexts.sqlite_client import initialized_test_database
from vedro import given, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.processor import MergeProcessor
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.models.mr import Author, MergeRequest


@scenario()
async def restart_recovery_continues_processing():
    """Test that system recovers gracefully after restart."""

    async with initialized_test_database() as db:
        with given("MRs stuck in various intermediate states after crash"):
            queue = QueueManager(db)
            await queue.ensure_schema()

            # Add MRs in different states to simulate mid-processing shutdown
            mrs_states = [
                (500, "queued"),
                (501, "rebasing"),
                (502, "testing"),
                (503, "merging"),
            ]

            for mr_iid, state in mrs_states:
                test_mr = MergeRequest(
                    iid=mr_iid,
                    title=f"MR {mr_iid} - {state}",
                    state="opened",
                    target_branch="main",
                    source_branch=f"feature/{mr_iid}",
                    sha=f"sha_{mr_iid}",
                    labels=["merge_queue"],
                    author=Author(id=mr_iid, name=f"User {mr_iid}", username=f"user{mr_iid}"),
                    merge_status="can_be_merged",
                    web_url=f"https://gitlab.com/test/project/-/merge_requests/{mr_iid}",
                )
                await queue.add_to_queue(test_mr, is_hotfix=False)
                if state != "queued":
                    await queue.update_mr_state(mr_iid, state)

            mock_url = get_mock_url()
            settings = created_test_settings(mock_url)

            # Mock list MRs response - all still open and labeled
            list_mrs_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests")
            list_mrs_response = jj.Response(
                status=200,
                json=[
                    {
                        "iid": mr_iid,
                        "state": "opened",
                        "labels": ["merge_queue"],
                        "sha": f"sha_{mr_iid}",
                    }
                    for mr_iid, _ in mrs_states
                ],
            )

            # Individual MR matchers
            mr_matchers = []
            for mr_iid, state in mrs_states:
                matcher = jj.match("GET", f"/api/v4/projects/123/merge_requests/{mr_iid}")
                response = jj.Response(
                    status=200,
                    json={
                        "iid": mr_iid,
                        "project_id": 123,
                        "title": f"MR {mr_iid} - {state}",
                        "state": "opened",
                        "sha": f"sha_{mr_iid}",
                        "labels": ["merge_queue"],
                        "source_branch": f"feature/{mr_iid}",
                        "target_branch": "main",
                        "merge_status": "can_be_merged",
                        "author": {
                            "id": mr_iid,
                            "name": f"User {mr_iid}",
                            "username": f"user{mr_iid}",
                        },
                    },
                )
                mr_matchers.append((matcher, response))

            # GET notes (for finding existing bot comments)
            get_notes_matcher = jj.match(
                "GET", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes")
            )
            get_notes_response = jj.Response(status=200, json=[])

            # POST notes (for creating new comments)
            comment_matcher = jj.match(
                "POST", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes")
            )
            comment_response = jj.Response(status=201, json={"id": 1})

        async with (
            mocked(list_mrs_matcher, list_mrs_response),
            mocked(mr_matchers[0][0], mr_matchers[0][1]),
            mocked(mr_matchers[1][0], mr_matchers[1][1]),
            mocked(mr_matchers[2][0], mr_matchers[2][1]),
            mocked(mr_matchers[3][0], mr_matchers[3][1]),
            mocked(get_notes_matcher, get_notes_response),
            mocked(comment_matcher, comment_response),
        ):
            with when("system shuts down and restarts"):
                gitlab_client = GitLabClient(settings)
                notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)

                # Simulate first processor that crashes
                processor_1 = MergeProcessor(
                    gitlab_client=gitlab_client,
                    queue_manager=queue,
                    notifier=notifier,
                    settings=settings,
                )

                # Request shutdown (simulating graceful stop)
                processor_1.request_shutdown()

                # Simulate restart with new processor instance
                processor_2 = MergeProcessor(
                    gitlab_client=gitlab_client,
                    queue_manager=queue,
                    notifier=notifier,
                    settings=settings,
                )

                # Run recovery
                await processor_2._recover_interrupted_state()

                # Get recovered states
                recovered_states = {}
                for mr_iid, _ in mrs_states:
                    state_data = await queue.get_mr_state(mr_iid)
                    recovered_states[mr_iid] = state_data["status"] if state_data else None

            with then("all intermediate states reset to queued"):
                # All intermediate states should be reset to queued
                assert recovered_states[500] == "queued", "Queued should remain queued"
                assert recovered_states[501] == "queued", "Rebasing should reset to queued"
                assert recovered_states[502] == "queued", "Testing should reset to queued"
                assert recovered_states[503] == "queued", "Merging should reset to queued"

                # Verify queue is ready for processing
                next_mr = await queue.get_next_mr()
                assert next_mr is not None, "Queue should have MRs ready"
                assert next_mr.mr_iid == 500, "First MR should be next (FIFO order)"


@scenario()
async def restart_detects_merged_mr_in_gitlab():
    """Test that recovery detects MRs that were merged in GitLab during downtime."""

    async with initialized_test_database() as db:
        with given("MR in 'merging' state but already merged in GitLab"):
            queue = QueueManager(db)
            await queue.ensure_schema()

            # Add MR that's in "merging" state locally
            test_mr = MergeRequest(
                iid=600,
                title="Almost Merged",
                state="opened",
                target_branch="main",
                source_branch="feature/600",
                sha="sha_600",
                labels=["merge_queue"],
                author=Author(id=600, name="User 600", username="user600"),
                merge_status="can_be_merged",
                web_url="https://gitlab.com/test/project/-/merge_requests/600",
            )
            await queue.add_to_queue(test_mr, is_hotfix=False)
            await queue.update_mr_state(600, "merging")

            mock_url = get_mock_url()
            settings = created_test_settings(mock_url)

            # Mock: GitLab says MR is now merged
            get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/600")
            get_mr_response = jj.Response(
                status=200,
                json={
                    "iid": 600,
                    "project_id": 123,
                    "title": "Almost Merged",
                    "state": "merged",  # Already merged in GitLab
                    "sha": "sha_600",
                    "labels": [],  # Labels removed after merge
                    "source_branch": "feature/600",
                    "target_branch": "main",
                    "merge_status": "can_be_merged",
                    "author": {"id": 600, "name": "User 600", "username": "user600"},
                },
            )

            list_mrs_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests")
            list_mrs_response = jj.Response(status=200, json=[])

            # GET notes (for finding existing bot comments)
            get_notes_matcher = jj.match(
                "GET", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes")
            )
            get_notes_response = jj.Response(status=200, json=[])

            # POST notes (for creating new comments)
            comment_matcher = jj.match(
                "POST", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes")
            )
            comment_response = jj.Response(status=201, json={"id": 1})

        async with (
            mocked(get_mr_matcher, get_mr_response),
            mocked(list_mrs_matcher, list_mrs_response),
            mocked(get_notes_matcher, get_notes_response),
            mocked(comment_matcher, comment_response),
        ):
            with when("processor runs recovery"):
                gitlab_client = GitLabClient(settings)
                notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
                processor = MergeProcessor(
                    gitlab_client=gitlab_client,
                    queue_manager=queue,
                    notifier=notifier,
                    settings=settings,
                )

                await processor._recover_interrupted_state()
                state_data = await queue.get_mr_state(600)
                final_state = state_data["status"] if state_data else None

            with then("MR is marked as merged"):
                assert final_state == "merged", "MR should be marked as merged"

                # Queue should be empty
                next_mr = await queue.get_next_mr()
                assert next_mr is None, "Queue should be empty"


@scenario()
async def restart_detects_closed_mr_in_gitlab():
    """Test that recovery detects MRs that were closed in GitLab during downtime."""

    async with initialized_test_database() as db:
        with given("MR in 'testing' state but closed in GitLab"):
            queue = QueueManager(db)
            await queue.ensure_schema()

            test_mr = MergeRequest(
                iid=700,
                title="Closed MR",
                state="opened",
                target_branch="main",
                source_branch="feature/700",
                sha="sha_700",
                labels=["merge_queue"],
                author=Author(id=700, name="User 700", username="user700"),
                merge_status="can_be_merged",
                web_url="https://gitlab.com/test/project/-/merge_requests/700",
            )
            await queue.add_to_queue(test_mr, is_hotfix=False)
            await queue.update_mr_state(700, "testing")

            mock_url = get_mock_url()
            settings = created_test_settings(mock_url)

            # Mock: GitLab says MR is now closed
            get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/700")
            get_mr_response = jj.Response(
                status=200,
                json={
                    "iid": 700,
                    "project_id": 123,
                    "title": "Closed MR",
                    "state": "closed",  # Closed in GitLab
                    "sha": "sha_700",
                    "labels": ["merge_queue"],
                    "source_branch": "feature/700",
                    "target_branch": "main",
                    "merge_status": "can_be_merged",
                    "author": {"id": 700, "name": "User 700", "username": "user700"},
                },
            )

            list_mrs_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests")
            list_mrs_response = jj.Response(status=200, json=[])

            # GET notes (for finding existing bot comments)
            get_notes_matcher = jj.match(
                "GET", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes")
            )
            get_notes_response = jj.Response(status=200, json=[])

            # POST notes (for creating new comments)
            comment_matcher = jj.match(
                "POST", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes")
            )
            comment_response = jj.Response(status=201, json={"id": 1})

        async with (
            mocked(get_mr_matcher, get_mr_response),
            mocked(list_mrs_matcher, list_mrs_response),
            mocked(get_notes_matcher, get_notes_response),
            mocked(comment_matcher, comment_response),
        ):
            with when("processor runs recovery"):
                gitlab_client = GitLabClient(settings)
                notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
                processor = MergeProcessor(
                    gitlab_client=gitlab_client,
                    queue_manager=queue,
                    notifier=notifier,
                    settings=settings,
                )

                await processor._recover_interrupted_state()
                state_data = await queue.get_mr_state(700)
                final_state = state_data["status"] if state_data else None

            with then("MR is marked as removed"):
                assert final_state == "removed", "MR should be marked as removed"


__all__ = [
    "restart_detects_closed_mr_in_gitlab",
    "restart_detects_merged_mr_in_gitlab",
    "restart_recovery_continues_processing",
]
