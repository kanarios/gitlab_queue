"""Integration test scenario for hotfix priority in merge queue.

This scenario tests that hotfix MRs jump to the front of the queue:
1. Regular MRs are already in queue
2. Hotfix arrives
3. Hotfix is processed first
4. Regular MRs continue in original order
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


def create_mr_data(mr_iid: int, is_hotfix: bool = False, project_id: int = 123) -> dict:
    """Create MR data dict for JJ mock responses."""
    labels = ["merge_queue"]
    if is_hotfix:
        labels.append("hotfix")

    return {
        "iid": mr_iid,
        "project_id": project_id,
        "title": "HOTFIX: Critical fix" if is_hotfix else f"Feature {mr_iid}",
        "state": "opened",
        "source_branch": "hotfix/critical" if is_hotfix else f"feature/{mr_iid}",
        "target_branch": "main",
        "sha": f"sha_{mr_iid}",
        "labels": labels,
        "author": {"id": mr_iid, "name": f"User {mr_iid}", "username": f"user{mr_iid}"},
        "merge_status": "can_be_merged",
        "web_url": f"https://gitlab.com/test/project/-/merge_requests/{mr_iid}",
    }


@scenario()
async def hotfix_jumps_to_front_of_queue():
    """Test that hotfix MR is processed before regular MRs."""

    async with test_database() as db:
        with given("2 regular MRs in queue, then hotfix arrives"):
            queue = QueueManager(db)
            await queue.ensure_schema()

            mock_url = get_mock_url()
            settings = create_test_settings(mock_url)

            # Add 2 regular MRs first
            for mr_iid in [10, 20]:
                mr_data = create_mr_data(mr_iid, is_hotfix=False)
                test_mr = MergeRequest(
                    iid=mr_iid,
                    title=mr_data["title"],
                    state="opened",
                    target_branch="main",
                    source_branch=mr_data["source_branch"],
                    sha=mr_data["sha"],
                    labels=mr_data["labels"],
                    author=Author(id=mr_iid, name=f"User {mr_iid}", username=f"user{mr_iid}"),
                    merge_status="can_be_merged",
                    web_url=mr_data["web_url"],
                )
                await queue.add_to_queue(test_mr, is_hotfix=False)

            # Add hotfix with priority
            hotfix_iid = 99
            hotfix_data = create_mr_data(hotfix_iid, is_hotfix=True)
            hotfix_mr = MergeRequest(
                iid=hotfix_iid,
                title=hotfix_data["title"],
                state="opened",
                target_branch="main",
                source_branch=hotfix_data["source_branch"],
                sha=hotfix_data["sha"],
                labels=hotfix_data["labels"],
                author=Author(id=hotfix_iid, name="Hotfix User", username="hotfix"),
                merge_status="can_be_merged",
                web_url=hotfix_data["web_url"],
            )
            await queue.add_to_queue(hotfix_mr, is_hotfix=True)

            # Create mock responses for all MRs
            mr_10_data = create_mr_data(10)
            mr_20_data = create_mr_data(20)

            # GET MR matchers
            get_mr_10_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/10")
            get_mr_10_response = jj.Response(status=200, json=mr_10_data)

            get_mr_20_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/20")
            get_mr_20_response = jj.Response(status=200, json=mr_20_data)

            get_mr_99_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/99")
            get_mr_99_response = jj.Response(status=200, json=hotfix_data)

            # Rebase matchers
            rebase_any_matcher = jj.match("PUT", r"/api/v4/projects/123/merge_requests/\d+/rebase")
            rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

            # Pipeline matchers
            pipelines_10_matcher = jj.match(
                "GET", "/api/v4/projects/123/merge_requests/10/pipelines"
            )
            pipelines_10_response = jj.Response(
                status=200, json=[{"id": 100, "status": "success", "sha": "sha_10"}]
            )

            pipelines_20_matcher = jj.match(
                "GET", "/api/v4/projects/123/merge_requests/20/pipelines"
            )
            pipelines_20_response = jj.Response(
                status=200, json=[{"id": 200, "status": "success", "sha": "sha_20"}]
            )

            pipelines_99_matcher = jj.match(
                "GET", "/api/v4/projects/123/merge_requests/99/pipelines"
            )
            pipelines_99_response = jj.Response(
                status=200, json=[{"id": 990, "status": "success", "sha": "sha_99"}]
            )

            # Merge matchers
            merge_10_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/10/merge")
            merge_10_response = jj.Response(status=200, json={**mr_10_data, "state": "merged"})

            merge_20_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/20/merge")
            merge_20_response = jj.Response(status=200, json={**mr_20_data, "state": "merged"})

            merge_99_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/99/merge")
            merge_99_response = jj.Response(status=200, json={**hotfix_data, "state": "merged"})

            # GET notes (for finding existing bot comments)
            get_notes_matcher = jj.match("GET", r"/api/v4/projects/123/merge_requests/\d+/notes")
            get_notes_response = jj.Response(status=200, json=[])

            # Comment matcher (generic)
            comment_matcher = jj.match("POST", r"/api/v4/projects/123/merge_requests/\d+/notes")
            comment_response = jj.Response(status=201, json={"id": 1})

        async with (
            mocked(get_mr_10_matcher, get_mr_10_response),
            mocked(get_mr_20_matcher, get_mr_20_response),
            mocked(get_mr_99_matcher, get_mr_99_response),
            mocked(rebase_any_matcher, rebase_response),
            mocked(pipelines_10_matcher, pipelines_10_response),
            mocked(pipelines_20_matcher, pipelines_20_response),
            mocked(pipelines_99_matcher, pipelines_99_response),
            mocked(merge_10_matcher, merge_10_response) as merge_10_mock,
            mocked(merge_20_matcher, merge_20_response) as merge_20_mock,
            mocked(merge_99_matcher, merge_99_response) as merge_99_mock,
            mocked(get_notes_matcher, get_notes_response),
            mocked(comment_matcher, comment_response),
        ):
            with when("processor runs one cycle"):
                gitlab_client = GitLabClient(settings)
                notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
                processor = MergeProcessor(
                    gitlab_client=gitlab_client,
                    queue_manager=queue,
                    notifier=notifier,
                    settings=settings,
                )

                # Process first MR - should be hotfix
                first_mr = await queue.get_next_mr()
                first_result = await processor._process_mr(first_mr)

            with then("hotfix is processed first"):
                # Verify hotfix was first
                assert first_mr.mr_iid == 99, "Hotfix should be processed first"
                assert first_result.value == "success", "Hotfix should merge successfully"

                # Verify hotfix merge was called
                merge_99_history = await merge_99_mock.fetch_history()
                assert len(merge_99_history) == 1, "Hotfix should be merged"

                # Verify regular MRs haven't been merged yet
                merge_10_history = await merge_10_mock.fetch_history()
                merge_20_history = await merge_20_mock.fetch_history()
                assert len(merge_10_history) == 0, "MR 10 should not be merged yet"
                assert len(merge_20_history) == 0, "MR 20 should not be merged yet"

                # Verify queue order for remaining MRs
                next_mr = await queue.get_next_mr()
                assert next_mr.mr_iid == 10, "MR 10 should be next (FIFO order)"


@scenario()
async def hotfix_priority_with_processing_continues():
    """Test that after hotfix, regular MRs continue in FIFO order."""

    async with test_database() as db:
        with given("2 regular MRs and 1 hotfix in queue"):
            queue = QueueManager(db)
            await queue.ensure_schema()

            mock_url = get_mock_url()
            settings = create_test_settings(mock_url)

            # Add regular MR 10
            mr_10 = MergeRequest(
                iid=10,
                title="Feature 10",
                state="opened",
                target_branch="main",
                source_branch="feature/10",
                sha="sha_10",
                labels=["merge_queue"],
                author=Author(id=10, name="User 10", username="user10"),
                merge_status="can_be_merged",
                web_url="https://gitlab.com/test/project/-/merge_requests/10",
            )
            await queue.add_to_queue(mr_10, is_hotfix=False)

            # Add regular MR 20
            mr_20 = MergeRequest(
                iid=20,
                title="Feature 20",
                state="opened",
                target_branch="main",
                source_branch="feature/20",
                sha="sha_20",
                labels=["merge_queue"],
                author=Author(id=20, name="User 20", username="user20"),
                merge_status="can_be_merged",
                web_url="https://gitlab.com/test/project/-/merge_requests/20",
            )
            await queue.add_to_queue(mr_20, is_hotfix=False)

            # Add hotfix
            hotfix = MergeRequest(
                iid=99,
                title="HOTFIX: Critical",
                state="opened",
                target_branch="main",
                source_branch="hotfix/critical",
                sha="sha_99",
                labels=["merge_queue", "hotfix"],
                author=Author(id=99, name="Hotfix User", username="hotfix"),
                merge_status="can_be_merged",
                web_url="https://gitlab.com/test/project/-/merge_requests/99",
            )
            await queue.add_to_queue(hotfix, is_hotfix=True)

            # Setup mocks for all MRs
            get_mr_matcher = jj.match("GET", r"/api/v4/projects/123/merge_requests/\d+")

            rebase_matcher = jj.match("PUT", r"/api/v4/projects/123/merge_requests/\d+/rebase")
            rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

            pipelines_matcher = jj.match(
                "GET", r"/api/v4/projects/123/merge_requests/\d+/pipelines"
            )
            pipelines_response = jj.Response(
                status=200, json=[{"id": 1, "status": "success", "sha": "sha"}]
            )

            merge_matcher = jj.match("PUT", r"/api/v4/projects/123/merge_requests/\d+/merge")
            merge_response = jj.Response(status=200, json={"state": "merged"})

            # GET notes (for finding existing bot comments)
            get_notes_matcher = jj.match("GET", r"/api/v4/projects/123/merge_requests/\d+/notes")
            get_notes_response = jj.Response(status=200, json=[])

            comment_matcher = jj.match("POST", r"/api/v4/projects/123/merge_requests/\d+/notes")
            comment_response = jj.Response(status=201, json={"id": 1})

        async with (
            mocked(
                get_mr_matcher,
                jj.Response(
                    status=200, json={"iid": 1, "state": "opened", "labels": ["merge_queue"]}
                ),
            ),
            mocked(rebase_matcher, rebase_response),
            mocked(pipelines_matcher, pipelines_response),
            mocked(merge_matcher, merge_response) as merge_mock,
            mocked(get_notes_matcher, get_notes_response),
            mocked(comment_matcher, comment_response),
        ):
            with when("processor processes all MRs"):
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
                    await processor._process_mr(queue_item)
                    processed_order.append(queue_item.mr_iid)

            with then("hotfix first, then regular MRs in FIFO order"):
                # Verify order: hotfix (99), then 10, then 20
                assert processed_order == [
                    99,
                    10,
                    20,
                ], f"Expected [99, 10, 20], got {processed_order}"

                # Verify all were merged
                merge_history = await merge_mock.fetch_history()
                assert len(merge_history) == 3, "All 3 MRs should be merged"


__all__ = [
    "hotfix_jumps_to_front_of_queue",
    "hotfix_priority_with_processing_continues",
]
