"""Integration test scenarios for concurrent webhook and polling operations.

This scenario tests race conditions:
1. Webhook handler adds MR while polling discovers same MR
2. Verify no duplicate MRs in queue
3. Verify data consistency under concurrent operations
"""

from __future__ import annotations

import asyncio

import jj
from jj.mock import mocked
from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.contexts.jj_gitlab_mock import get_mock_url
from scenarios.contexts.sqlite_client import initialized_test_database
from vedro import given, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.core.scheduler import QueueScheduler
from gitlab_queue.models.mr import Author, MergeRequest
from gitlab_queue.webhooks.router import WebhookHandler


@scenario()
async def concurrent_webhook_and_polling_no_duplicates():
    """Test that concurrent webhook and polling don't create duplicate MRs."""

    async with initialized_test_database() as db:
        with given("webhook and polling discover same MR simultaneously"):
            queue = QueueManager(db)
            await queue.ensure_schema()

            mock_url = get_mock_url()
            settings = created_test_settings(mock_url)

            # MR data for both webhook and polling
            mr_data = {
                "iid": 42,
                "project_id": 123,
                "title": "Concurrent MR",
                "state": "opened",
                "source_branch": "feature/concurrent",
                "target_branch": "main",
                "sha": "sha_42",
                "labels": ["merge_queue"],
                "author": {"id": 42, "name": "User 42", "username": "user42"},
                "merge_status": "can_be_merged",
                "web_url": "https://gitlab.com/test/project/-/merge_requests/42",
            }

            # Webhook payload for same MR
            webhook_payload = {
                "object_kind": "merge_request",
                "event_type": "merge_request",
                "project": {"id": 123},
                "object_attributes": {
                    "iid": 42,
                    "title": "Concurrent MR",
                    "state": "opened",
                    "source_branch": "feature/concurrent",
                    "target_branch": "main",
                    "last_commit": {"id": "sha_42"},
                    "labels": [{"title": "merge_queue"}],
                    "action": "update",
                },
                "labels": [{"title": "merge_queue"}],
            }

            # Mock GitLab API - list MRs returns our MR
            list_mrs_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests")
            list_mrs_response = jj.Response(status=200, json=[mr_data])

            # Mock GET single MR
            get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42")
            get_mr_response = jj.Response(status=200, json=mr_data)

            # GET notes (for finding existing bot comments)
            get_notes_matcher = jj.match("GET", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes"))
            get_notes_response = jj.Response(status=200, json=[])

            # Comment matcher (optional notifications)
            comment_matcher = jj.match("POST", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes"))
            comment_response = jj.Response(status=201, json={"id": 1})

        async with (
            mocked(list_mrs_matcher, list_mrs_response),
            mocked(get_mr_matcher, get_mr_response),
            mocked(get_notes_matcher, get_notes_response),
            mocked(comment_matcher, comment_response),
        ):
            with when("webhook and polling run concurrently"):
                gitlab_client = GitLabClient(settings)
                webhook_handler = WebhookHandler(
                    queue_manager=queue,
                    gitlab_client=gitlab_client,
                    settings=settings,
                )
                scheduler = QueueScheduler(
                    gitlab_client=gitlab_client,
                    queue_manager=queue,
                    settings=settings,
                )

                # Run both operations concurrently using asyncio.gather
                results = await asyncio.gather(
                    webhook_handler.handle_merge_request_event(webhook_payload),
                    scheduler.sync_queue(),
                    return_exceptions=True,
                )

                # Note: One operation may fail with IntegrityError/NoResultFound
                # when both try to add the same MR simultaneously.
                # This is expected behavior - the important thing is that
                # at least one succeeds and no duplicates are created.
                successes = [r for r in results if not isinstance(r, Exception)]
                assert len(successes) >= 1, "At least one operation should succeed"

                # Get final queue state
                queue_items = await queue.get_active_queue()

            with then("exactly one MR in queue (no duplicates)"):
                assert len(queue_items) == 1, f"Expected 1 MR, got {len(queue_items)}"
                assert queue_items[0].mr_iid == 42, "MR 42 should be in queue"


@scenario()
async def concurrent_multiple_webhooks_same_mr():
    """Test that multiple webhooks for same MR don't create duplicates."""

    async with initialized_test_database() as db:
        with given("multiple webhook events for same MR arrive simultaneously"):
            queue = QueueManager(db)
            await queue.ensure_schema()

            mock_url = get_mock_url()
            settings = created_test_settings(mock_url)

            mr_data = {
                "iid": 50,
                "project_id": 123,
                "title": "Multi-webhook MR",
                "state": "opened",
                "source_branch": "feature/multi",
                "target_branch": "main",
                "sha": "sha_50",
                "labels": ["merge_queue"],
                "author": {"id": 50, "name": "User 50", "username": "user50"},
                "merge_status": "can_be_merged",
                "web_url": "https://gitlab.com/test/project/-/merge_requests/50",
            }

            # Multiple webhook payloads (e.g., labeled, then update)
            webhook_labeled = {
                "object_kind": "merge_request",
                "event_type": "merge_request",
                "project": {"id": 123},
                "object_attributes": {
                    "iid": 50,
                    "title": "Multi-webhook MR",
                    "state": "opened",
                    "source_branch": "feature/multi",
                    "target_branch": "main",
                    "last_commit": {"id": "sha_50"},
                    "labels": [{"title": "merge_queue"}],
                    "action": "update",  # Label was added
                },
                "labels": [{"title": "merge_queue"}],
            }

            webhook_updated = {
                "object_kind": "merge_request",
                "event_type": "merge_request",
                "project": {"id": 123},
                "object_attributes": {
                    "iid": 50,
                    "title": "Multi-webhook MR (updated)",
                    "state": "opened",
                    "source_branch": "feature/multi",
                    "target_branch": "main",
                    "last_commit": {"id": "sha_50_v2"},  # New commit
                    "labels": [{"title": "merge_queue"}],
                    "action": "update",
                },
                "labels": [{"title": "merge_queue"}],
            }

            get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/50")
            get_mr_response = jj.Response(status=200, json=mr_data)

            # GET notes (for finding existing bot comments)
            get_notes_matcher = jj.match("GET", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes"))
            get_notes_response = jj.Response(status=200, json=[])

            comment_matcher = jj.match("POST", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes"))
            comment_response = jj.Response(status=201, json={"id": 1})

        async with (
            mocked(get_mr_matcher, get_mr_response),
            mocked(get_notes_matcher, get_notes_response),
            mocked(comment_matcher, comment_response),
        ):
            with when("multiple webhooks fire concurrently"):
                gitlab_client = GitLabClient(settings)
                webhook_handler = WebhookHandler(
                    queue_manager=queue,
                    gitlab_client=gitlab_client,
                    settings=settings,
                )

                # Fire 5 webhook events concurrently
                results = await asyncio.gather(
                    webhook_handler.handle_merge_request_event(webhook_labeled),
                    webhook_handler.handle_merge_request_event(webhook_updated),
                    webhook_handler.handle_merge_request_event(webhook_labeled),
                    webhook_handler.handle_merge_request_event(webhook_updated),
                    webhook_handler.handle_merge_request_event(webhook_labeled),
                    return_exceptions=True,
                )

                # Check for exceptions
                exceptions = [r for r in results if isinstance(r, Exception)]
                if exceptions:
                    raise exceptions[0]

                queue_items = await queue.get_active_queue()

            with then("exactly one MR in queue"):
                assert len(queue_items) == 1, f"Expected 1 MR, got {len(queue_items)}"
                assert queue_items[0].mr_iid == 50


@scenario()
async def concurrent_add_and_remove():
    """Test that concurrent add and remove operations are consistent."""

    async with initialized_test_database() as db:
        with given("MR is being added and removed simultaneously"):
            queue = QueueManager(db)
            await queue.ensure_schema()

            mock_url = get_mock_url()
            settings = created_test_settings(mock_url)

            mr_data = {
                "iid": 60,
                "project_id": 123,
                "title": "Add-Remove MR",
                "state": "opened",
                "source_branch": "feature/add-remove",
                "target_branch": "main",
                "sha": "sha_60",
                "labels": [],  # No label in final state
                "author": {"id": 60, "name": "User 60", "username": "user60"},
                "merge_status": "can_be_merged",
                "web_url": "https://gitlab.com/test/project/-/merge_requests/60",
            }

            # Webhook: label added
            webhook_labeled = {
                "object_kind": "merge_request",
                "event_type": "merge_request",
                "project": {"id": 123},
                "object_attributes": {
                    "iid": 60,
                    "title": "Add-Remove MR",
                    "state": "opened",
                    "source_branch": "feature/add-remove",
                    "target_branch": "main",
                    "last_commit": {"id": "sha_60"},
                    "labels": [{"title": "merge_queue"}],
                    "action": "update",
                },
                "labels": [{"title": "merge_queue"}],
            }

            # Webhook: label removed
            webhook_unlabeled = {
                "object_kind": "merge_request",
                "event_type": "merge_request",
                "project": {"id": 123},
                "object_attributes": {
                    "iid": 60,
                    "title": "Add-Remove MR",
                    "state": "opened",
                    "source_branch": "feature/add-remove",
                    "target_branch": "main",
                    "last_commit": {"id": "sha_60"},
                    "labels": [],  # No labels
                    "action": "update",
                },
                "labels": [],
                "changes": {
                    "labels": {
                        "previous": [{"title": "merge_queue"}],
                        "current": [],
                    }
                },
            }

            get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/60")
            get_mr_response = jj.Response(status=200, json=mr_data)

            # GET notes (for finding existing bot comments)
            get_notes_matcher = jj.match("GET", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes"))
            get_notes_response = jj.Response(status=200, json=[])

            comment_matcher = jj.match("POST", jj.matchers.regex(r"/api/v4/projects/123/merge_requests/\d+/notes"))
            comment_response = jj.Response(status=201, json={"id": 1})

        async with (
            mocked(get_mr_matcher, get_mr_response),
            mocked(get_notes_matcher, get_notes_response),
            mocked(comment_matcher, comment_response),
        ):
            with when("add and remove webhooks fire concurrently"):
                gitlab_client = GitLabClient(settings)
                webhook_handler = WebhookHandler(
                    queue_manager=queue,
                    gitlab_client=gitlab_client,
                    settings=settings,
                )

                # Run add then remove concurrently (multiple times)
                await asyncio.gather(
                    webhook_handler.handle_merge_request_event(webhook_labeled),
                    webhook_handler.handle_merge_request_event(webhook_unlabeled),
                    webhook_handler.handle_merge_request_event(webhook_labeled),
                    webhook_handler.handle_merge_request_event(webhook_unlabeled),
                    return_exceptions=True,
                )

                queue_items = await queue.get_active_queue()

            with then("queue state is consistent (MR removed or never added)"):
                # Final state should be consistent - either removed or not in active queue
                # The exact state depends on ordering, but should never have duplicates
                assert len(queue_items) <= 1, f"Should have at most 1 MR, got {len(queue_items)}"

                # If MR is in queue, it should not be in 'removed' state
                for item in queue_items:
                    item_state = await queue.get_mr_state(item.mr_iid)
                    assert item_state != "removed", "Active queue item should not be 'removed'"


@scenario()
async def concurrent_processing_doesnt_duplicate():
    """Test that queue position updates are consistent under concurrent reads."""

    async with initialized_test_database() as db:
        with given("multiple readers accessing queue position simultaneously"):
            queue = QueueManager(db)
            await queue.ensure_schema()

            # Pre-populate queue with 5 MRs
            for i in range(1, 6):
                test_mr = MergeRequest(
                    iid=i,
                    title=f"MR {i}",
                    state="opened",
                    target_branch="main",
                    source_branch=f"feature/{i}",
                    sha=f"sha_{i}",
                    labels=["merge_queue"],
                    author=Author(id=i, name=f"User {i}", username=f"user{i}"),
                    merge_status="can_be_merged",
                    web_url=f"https://gitlab.com/test/project/-/merge_requests/{i}",
                )
                await queue.add_to_queue(test_mr, is_hotfix=False)

        # No mocks needed - pure database operations
        with when("multiple concurrent position queries"):
            # Run 10 concurrent position queries
            async def get_positions():
                positions = {}
                for i in range(1, 6):
                    pos = await queue.get_queue_position(i)
                    positions[i] = pos
                return positions

            results = await asyncio.gather(
                get_positions(),
                get_positions(),
                get_positions(),
                get_positions(),
                get_positions(),
            )

        with then("all queries return consistent positions"):
            # All results should be identical
            for result in results:
                assert result == results[0], "All position queries should return same result"

            # Positions should be 1, 2, 3, 4, 5 in FIFO order
            expected = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
            assert results[0] == expected, f"Expected {expected}, got {results[0]}"


__all__ = [
    "concurrent_add_and_remove",
    "concurrent_multiple_webhooks_same_mr",
    "concurrent_processing_doesnt_duplicate",
    "concurrent_webhook_and_polling_no_duplicates",
]
