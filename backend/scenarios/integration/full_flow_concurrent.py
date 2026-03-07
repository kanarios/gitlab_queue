"""Integration test scenarios for concurrent webhook and polling operations.

This scenario tests race conditions:
1. Webhook handler adds MR while polling discovers same MR
2. Verify no duplicate MRs in queue
3. Verify data consistency under concurrent operations
"""

from __future__ import annotations

import asyncio
import re

from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.transports import GitLabMockTransport
from sqlalchemy.exc import IntegrityError, NoResultFound
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

            transport = GitLabMockTransport()
            settings = created_test_settings()

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

            # Register GitLab API responses
            transport.register_get(
                "/api/v4/projects/123/merge_requests",
                json_data=[mr_data],
            )

            transport.register_get(
                "/api/v4/projects/123/merge_requests/42",
                json_data=mr_data,
            )

            # GET notes (for finding existing bot comments)
            transport.register_get(
                re.compile(r"/api/v4/projects/123/merge_requests/\d+/notes"),
                json_data=[],
            )

            # POST notes (for creating new comments)
            transport.register_post(
                re.compile(r"/api/v4/projects/123/merge_requests/\d+/notes"),
                status=201,
                json_data={"id": 1},
            )

        with when("webhook and polling run concurrently"):
            gitlab_client = GitLabClient(settings, transport=transport)
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
            # Only IntegrityError/NoResultFound are acceptable - other exceptions are bugs.
            expected_race_errors = (IntegrityError, NoResultFound)
            unexpected = [r for r in results if isinstance(r, Exception) and not isinstance(r, expected_race_errors)]
            if unexpected:
                raise unexpected[0]
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

            transport = GitLabMockTransport()
            settings = created_test_settings()

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

            transport.register_get(
                "/api/v4/projects/123/merge_requests/50",
                json_data=mr_data,
            )

            # GET notes (for finding existing bot comments)
            transport.register_get(
                re.compile(r"/api/v4/projects/123/merge_requests/\d+/notes"),
                json_data=[],
            )

            # POST notes (for creating new comments)
            transport.register_post(
                re.compile(r"/api/v4/projects/123/merge_requests/\d+/notes"),
                status=201,
                json_data={"id": 1},
            )

        with when("multiple webhooks fire concurrently"):
            gitlab_client = GitLabClient(settings, transport=transport)
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

            # Note: Some operations may fail with IntegrityError/race conditions
            # when multiple webhooks process the same MR simultaneously.
            # This is expected - the key assertion is: no duplicates created.
            # Only IntegrityError/NoResultFound are acceptable - other exceptions are bugs.
            expected_race_errors = (IntegrityError, NoResultFound)
            unexpected = [r for r in results if isinstance(r, Exception) and not isinstance(r, expected_race_errors)]
            if unexpected:
                raise unexpected[0]
            successes = [r for r in results if not isinstance(r, Exception)]
            assert len(successes) >= 1, "At least one webhook should succeed"

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

            transport = GitLabMockTransport()
            settings = created_test_settings()

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

            transport.register_get(
                "/api/v4/projects/123/merge_requests/60",
                json_data=mr_data,
            )

            # GET notes (for finding existing bot comments)
            transport.register_get(
                re.compile(r"/api/v4/projects/123/merge_requests/\d+/notes"),
                json_data=[],
            )

            # POST notes (for creating new comments)
            transport.register_post(
                re.compile(r"/api/v4/projects/123/merge_requests/\d+/notes"),
                status=201,
                json_data={"id": 1},
            )

        with when("add and remove webhooks fire concurrently"):
            gitlab_client = GitLabClient(settings, transport=transport)
            webhook_handler = WebhookHandler(
                queue_manager=queue,
                gitlab_client=gitlab_client,
                settings=settings,
            )

            # Run add then remove concurrently (multiple times)
            results = await asyncio.gather(
                webhook_handler.handle_merge_request_event(webhook_labeled),
                webhook_handler.handle_merge_request_event(webhook_unlabeled),
                webhook_handler.handle_merge_request_event(webhook_labeled),
                webhook_handler.handle_merge_request_event(webhook_unlabeled),
                return_exceptions=True,
            )
            # Note: Some operations may fail with IntegrityError/NoResultFound
            # when add and remove race on the same MR simultaneously.
            # This is expected - the key assertion is: consistent final state.
            expected_race_errors = (IntegrityError, NoResultFound)
            unexpected = [r for r in results if isinstance(r, Exception) and not isinstance(r, expected_race_errors)]
            if unexpected:
                raise unexpected[0]

            successes = [r for r in results if not isinstance(r, Exception)]
            assert len(successes) >= 1

            queue_items = await queue.get_active_queue()

        with then("queue state is consistent (MR removed or never added)"):
            # Final state should be consistent - either removed or not in active queue
            # The exact state depends on ordering, but should never have duplicates
            assert len(queue_items) <= 1, f"Should have at most 1 MR, got {len(queue_items)}"

            # If MR is in queue, it should not be in 'removed' state
            for item in queue_items:
                item_state = await queue.get_mr_state(item.mr_iid)
                assert item_state is not None
                assert item_state["status"] != "removed", "Active queue item should not be 'removed'"


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
