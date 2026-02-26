"""Integration test scenario for multiple MRs processed in FIFO order.

This scenario tests the full system flow with multiple MRs:
1. Multiple MRs added to queue
2. Processing in FIFO order
3. Complete rebase -> pipeline -> merge workflow for each
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


def create_mr_mock(mr_iid: int, project_id: int = 123) -> dict:
    """Helper to create JJ matchers and responses for a single MR."""
    mr_data = {
        "iid": mr_iid,
        "project_id": project_id,
        "title": f"MR #{mr_iid}",
        "state": "opened",
        "source_branch": f"feature/{mr_iid}",
        "target_branch": "main",
        "sha": f"sha_{mr_iid}",
        "labels": ["merge_queue"],
        "author": {"id": mr_iid, "name": f"User {mr_iid}", "username": f"user{mr_iid}"},
        "merge_status": "can_be_merged",
        "web_url": f"https://gitlab.com/test/project/-/merge_requests/{mr_iid}",
    }
    pipeline_data = {"id": mr_iid * 10, "status": "success", "sha": f"sha_{mr_iid}"}

    return {
        "data": mr_data,
        "pipeline": pipeline_data,
        "get_mr": (
            jj.match("GET", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}"),
            jj.Response(status=200, json=mr_data),
        ),
        "rebase": (
            jj.match("PUT", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/rebase"),
            jj.Response(status=202, json={"rebase_in_progress": False}),
        ),
        "pipelines": (
            jj.match("GET", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/pipelines"),
            jj.Response(status=200, json=[pipeline_data]),
        ),
        "merge": (
            jj.match("PUT", f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/merge"),
            jj.Response(status=200, json={**mr_data, "state": "merged"}),
        ),
    }


@scenario()
async def process_multiple_mrs_in_order():
    """Test that multiple MRs are processed in FIFO order."""

    # Database must stay open for entire test
    async with initialized_test_database() as db:
        with given("3 MRs added to queue in order"):
            queue = QueueManager(db)
            await queue.ensure_schema()

            mock_url = get_mock_url()
            settings = created_test_settings(mock_url)

            # Create mock data for 3 MRs
            mr_mocks = {iid: create_mr_mock(iid) for iid in [10, 20, 30]}

            # Add MRs to queue in order
            for mr_iid in [10, 20, 30]:
                test_mr = MergeRequest(
                    iid=mr_iid,
                    title=f"MR #{mr_iid}",
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

            # GET notes (for finding existing bot comments)
            get_notes_matcher = jj.match("GET", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes"))
            get_notes_response = jj.Response(status=200, json=[])

            # Generic comment matcher
            comment_matcher = jj.match("POST", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes"))
            comment_response = jj.Response(status=201, json={"id": 1})

            project_matcher = jj.match("GET", "/api/v4/projects/123")
            project_response = jj.Response(status=200, json={"id": 123, "web_url": f"{mock_url}/test/project"})

        # Setup all mocks
        async with (
            mocked(project_matcher, project_response),
            mocked(mr_mocks[10]["get_mr"][0], mr_mocks[10]["get_mr"][1]),
            mocked(mr_mocks[20]["get_mr"][0], mr_mocks[20]["get_mr"][1]),
            mocked(mr_mocks[30]["get_mr"][0], mr_mocks[30]["get_mr"][1]),
            mocked(mr_mocks[10]["rebase"][0], mr_mocks[10]["rebase"][1]),
            mocked(mr_mocks[20]["rebase"][0], mr_mocks[20]["rebase"][1]),
            mocked(mr_mocks[30]["rebase"][0], mr_mocks[30]["rebase"][1]),
            mocked(mr_mocks[10]["pipelines"][0], mr_mocks[10]["pipelines"][1]),
            mocked(mr_mocks[20]["pipelines"][0], mr_mocks[20]["pipelines"][1]),
            mocked(mr_mocks[30]["pipelines"][0], mr_mocks[30]["pipelines"][1]),
            mocked(mr_mocks[10]["merge"][0], mr_mocks[10]["merge"][1]) as merge_10_mock,
            mocked(mr_mocks[20]["merge"][0], mr_mocks[20]["merge"][1]) as merge_20_mock,
            mocked(mr_mocks[30]["merge"][0], mr_mocks[30]["merge"][1]) as merge_30_mock,
            mocked(get_notes_matcher, get_notes_response),
            mocked(comment_matcher, comment_response),
        ):
            with when("processor runs until queue empty"):
                gitlab_client = GitLabClient(settings)
                notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
                processor = MergeProcessor(
                    gitlab_client=gitlab_client,
                    queue_manager=queue,
                    notifier=notifier,
                    settings=settings,
                )

                processed_order = []
                while True:
                    queue_item = await queue.get_next_mr()
                    if queue_item is None:
                        break
                    result = await processor._process_mr(queue_item)
                    processed_order.append((queue_item.mr_iid, result))

            with then("all MRs merged in FIFO order"):
                # Verify processing order
                assert len(processed_order) == 3, "All 3 MRs should be processed"
                assert processed_order[0][0] == 10, "MR 10 should be first"
                assert processed_order[1][0] == 20, "MR 20 should be second"
                assert processed_order[2][0] == 30, "MR 30 should be third"

                # Verify all succeeded
                assert all(r[1].value == "success" for r in processed_order), "All should succeed"

                # Verify each MR was merged exactly once
                merge_10_history = await merge_10_mock.fetch_history()
                merge_20_history = await merge_20_mock.fetch_history()
                merge_30_history = await merge_30_mock.fetch_history()

                assert len(merge_10_history) == 1, "MR 10 should be merged once"
                assert len(merge_20_history) == 1, "MR 20 should be merged once"
                assert len(merge_30_history) == 1, "MR 30 should be merged once"

                # Verify queue is empty
                assert await queue.get_next_mr() is None, "Queue should be empty"


__all__ = [
    "process_multiple_mrs_in_order",
]
