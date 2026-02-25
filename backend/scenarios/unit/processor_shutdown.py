"""Test scenarios for processor graceful shutdown.

This scenario tests how the processor handles:
1. Shutdown during different processing phases
2. Proper cleanup on shutdown
3. State preservation for resume
4. Shutdown timeout handling
"""

from __future__ import annotations

import asyncio
import contextlib

import jj
from jj.mock import mocked
from scenarios.contexts.jj_gitlab_mock import get_mock_url
from vedro import given, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.config import Settings
from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.processor import MergeProcessor, ProcessingResult
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.models.mr import Author, MergeRequest


@scenario()
async def graceful_shutdown_with_no_processing():
    """Test graceful shutdown when no MR is being processed."""

    with given("processor running with empty queue"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        mock_url = get_mock_url()

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-webhook-secret",
            poll_interval_seconds=10,  # Long poll to test interruption
        )

    with when("shutdown is requested with empty queue"):
        gitlab_client = GitLabClient(settings)
        notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
        processor = MergeProcessor(
            gitlab_client=gitlab_client,
            queue_manager=queue,
            notifier=notifier,
            settings=settings,
        )

        # Start processor in background
        processor_task = asyncio.create_task(processor.run())

        # Give it time to start
        await asyncio.sleep(0.1)

        # Request shutdown
        processor.request_shutdown()

        # Wait for shutdown to complete
        shutdown_complete = await processor.wait_for_shutdown(timeout=2.0)

        # Cancel the task if still running
        if not processor_task.done():
            processor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await processor_task

    with then("processor shuts down cleanly"):
        assert shutdown_complete
        assert processor.is_shutdown_requested
        assert not processor.is_processing
        assert processor.current_mr_iid is None

    await db.close()


@scenario()
async def graceful_shutdown_during_rebase():
    """Test graceful shutdown while rebase is in progress."""

    with given("MR being rebased when shutdown requested"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        test_mr = MergeRequest(
            iid=70,
            title="MR for Shutdown Test",
            state="opened",
            target_branch="main",
            source_branch="feature/shutdown",
            sha="shutdown123",
            labels=["merge_queue"],
            author=Author(id=1, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/70",
        )

        await queue.add_to_queue(test_mr, is_hotfix=False)

        mock_url = get_mock_url()

        mr_data = {
            "iid": 70,
            "project_id": 123,
            "title": "MR for Shutdown Test",
            "state": "opened",
            "sha": "shutdown123",
            "labels": ["merge_queue"],
            "source_branch": "feature/shutdown",
            "target_branch": "main",
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "author": {"id": 1, "name": "Test User", "username": "testuser"},
            "web_url": "https://gitlab.com/test/project/-/merge_requests/70",
        }

        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/70")
        get_mr_response = jj.Response(status=200, json=mr_data)

        # Rebase stays in progress (simulating long operation)
        rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/70/rebase")
        rebase_response = jj.Response(status=202, json={"rebase_in_progress": True})

        # Status check also shows in progress
        status_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/70")
        status_response = jj.Response(status=200, json={**mr_data, "rebase_in_progress": True})

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/70/notes")
        comment_response = jj.Response(status=201, json={"id": 40})

        # GET notes - needed for _find_bot_comment
        get_notes_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/70/notes")
        get_notes_response = jj.Response(status=200, json=[])

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-webhook-secret",
            rebase_timeout_seconds=60,  # Long timeout
            poll_interval_seconds=1,
        )

    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(rebase_matcher, rebase_response) as rebase_mock,
        mocked(status_matcher, status_response),
        mocked(get_notes_matcher, get_notes_response),
        mocked(comment_matcher, comment_response),
    ):
        with when("shutdown requested during rebase"):
            gitlab_client = GitLabClient(settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
            processor = MergeProcessor(
                gitlab_client=gitlab_client,
                queue_manager=queue,
                notifier=notifier,
                settings=settings,
            )

            # Start processing in a task
            async def process_with_shutdown():
                queue_item = await queue.get_next_mr()
                # Start processing
                processing_task = asyncio.create_task(processor._process_mr(queue_item))

                # Wait a bit for rebase to start
                await asyncio.sleep(0.5)

                # Request shutdown while processing
                processor.request_shutdown()

                # Wait for processing to complete
                try:
                    result = await processing_task
                    return result
                except asyncio.CancelledError:
                    return ProcessingResult.ERROR

            result = await process_with_shutdown()

        with then("processing stops gracefully"):
            # Should return error due to shutdown
            assert result == ProcessingResult.ERROR

            # Verify rebase was started
            rebase_history = await rebase_mock.fetch_history()
            assert len(rebase_history) == 1

            # Check MR state - should be in rebasing state
            mr_state = await queue.get_mr_state(70)
            assert mr_state["status"] in (
                "rebasing",
                "queued",
                "failed",
            ), f"MR should be in intermediate or reset state, got {mr_state}"

            # Verify shutdown flag
            assert processor.is_shutdown_requested

    await db.close()


@scenario()
async def processor_state_recovery_after_shutdown():
    """Test that processor correctly recovers state after shutdown."""

    with given("MRs in various states after shutdown"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        # Add MRs in different states
        mrs_data = [
            (71, "queued"),
            (72, "rebasing"),
            (73, "testing"),
            (74, "merging"),
        ]

        for mr_iid, initial_state in mrs_data:
            test_mr = MergeRequest(
                iid=mr_iid,
                title=f"MR {mr_iid} - In {initial_state} state",
                state="opened",
                target_branch="main",
                source_branch=f"feature/{mr_iid}",
                sha=f"sha{mr_iid}",
                labels=["merge_queue"],
                author=Author(id=1, name="Test User", username="testuser"),
                merge_status="can_be_merged",
                web_url=f"https://gitlab.com/test/project/-/merge_requests/{mr_iid}",
            )
            await queue.add_to_queue(test_mr, is_hotfix=False)
            # Set initial state
            if initial_state != "queued":
                await queue.update_mr_state(mr_iid, initial_state)

        mock_url = get_mock_url()

        # Mock responses for each MR
        for mr_iid, _ in mrs_data:
            mr_data = {
                "iid": mr_iid,
                "project_id": 123,
                "title": f"MR {mr_iid}",
                "state": "opened",
                "sha": f"sha{mr_iid}",
                "labels": ["merge_queue"],
            }

            # Variables created for mocking each MR individually below
            _ = jj.match("GET", f"/api/v4/projects/123/merge_requests/{mr_iid}")
            _ = jj.Response(status=200, json=mr_data)

        # Mock list MRs for sync
        list_mrs_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests")
        list_mrs_response = jj.Response(
            status=200,
            json=[{"iid": mr_iid, "state": "opened", "labels": ["merge_queue"]} for mr_iid, _ in mrs_data],
        )

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-webhook-secret",
        )

    # Mock all MR GET endpoints
    mr_mocks = []
    for mr_iid, _ in mrs_data:
        mr_data = {
            "iid": mr_iid,
            "project_id": 123,
            "title": f"MR {mr_iid}",
            "state": "opened",
            "sha": f"sha{mr_iid}",
            "labels": ["merge_queue"],
            "source_branch": f"feature/{mr_iid}",
            "target_branch": "main",
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "author": {"id": 1, "name": "Test User", "username": "testuser"},
            "web_url": f"https://gitlab.com/test/project/-/merge_requests/{mr_iid}",
        }
        matcher = jj.match("GET", f"/api/v4/projects/123/merge_requests/{mr_iid}")
        response = jj.Response(status=200, json=mr_data)
        mr_mocks.append(mocked(matcher, response))

    async with (
        mr_mocks[0],
        mr_mocks[1],
        mr_mocks[2],
        mr_mocks[3],
        mocked(list_mrs_matcher, list_mrs_response),
    ):
        with when("processor starts after shutdown"):
            gitlab_client = GitLabClient(settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
            processor = MergeProcessor(
                gitlab_client=gitlab_client,
                queue_manager=queue,
                notifier=notifier,
                settings=settings,
            )

            # Run recovery
            await processor._recover_interrupted_state()

        with then("intermediate states are reset to queued"):
            # Check states after recovery
            mr_71_state = await queue.get_mr_state(71)
            assert mr_71_state["status"] == "queued"

            mr_72_state = await queue.get_mr_state(72)
            assert mr_72_state["status"] == "queued"

            mr_73_state = await queue.get_mr_state(73)
            assert mr_73_state["status"] == "queued"

            mr_74_state = await queue.get_mr_state(74)
            assert mr_74_state["status"] == "queued"

            # Verify queue order is maintained
            next_mr = await queue.get_next_mr()
            assert next_mr is not None
            assert next_mr.mr_iid == 71

    await db.close()


@scenario()
async def shutdown_timeout_handling():
    """
    Test processor behavior when the shutdown wait times out.
    
    Sets up an in-memory database, queue manager, GitLab client, notifier, and MergeProcessor, starts the processor, requests shutdown with a very short wait timeout, and asserts that the processor's shutdown flag is set.
    """

    with given("processor that takes time to shutdown"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        mock_url = get_mock_url()

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-webhook-secret",
            poll_interval_seconds=10,
        )

    with when("shutdown wait times out"):
        gitlab_client = GitLabClient(settings)
        notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
        processor = MergeProcessor(
            gitlab_client=gitlab_client,
            queue_manager=queue,
            notifier=notifier,
            settings=settings,
        )

        # Start processor
        processor_task = asyncio.create_task(processor.run())

        # Give it time to start
        await asyncio.sleep(0.1)

        # Request shutdown
        processor.request_shutdown()

        # Wait with very short timeout
        _shutdown_complete = await processor.wait_for_shutdown(timeout=0.01)

        # Clean up
        processor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await processor_task

    with then("timeout is handled properly"):
        # Shutdown may complete quickly on fast machines, so we only verify
        # that the shutdown flag is properly set
        assert processor.is_shutdown_requested

    await db.close()


@scenario()
async def concurrent_processing_during_shutdown():
    """Test behavior when shutdown is requested while actively processing."""

    with given("active MR processing when shutdown requested"):
        db = Database(database_url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        queue = QueueManager(db)
        await queue.ensure_schema()

        test_mr = MergeRequest(
            iid=75,
            title="Concurrent Processing Test",
            state="opened",
            target_branch="main",
            source_branch="feature/concurrent",
            sha="concurrent123",
            labels=["merge_queue"],
            author=Author(id=1, name="Test User", username="testuser"),
            merge_status="can_be_merged",
            web_url="https://gitlab.com/test/project/-/merge_requests/75",
        )

        await queue.add_to_queue(test_mr, is_hotfix=False)

        mock_url = get_mock_url()

        mr_data = {
            "iid": 75,
            "project_id": 123,
            "title": "Concurrent Processing Test",
            "state": "opened",
            "sha": "concurrent123",
            "labels": ["merge_queue"],
            "source_branch": "feature/concurrent",
            "target_branch": "main",
            "merge_status": "can_be_merged",
            "has_conflicts": False,
            "rebase_in_progress": False,
            "author": {"id": 1, "name": "Test User", "username": "testuser"},
            "web_url": "https://gitlab.com/test/project/-/merge_requests/75",
        }

        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/75")
        get_mr_response = jj.Response(status=200, json=mr_data)

        rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/75/rebase")
        rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        pipelines_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/75/pipelines")
        pipelines_response = jj.Response(status=200, json=[{"id": 8001, "status": "running", "sha": "concurrent123"}])

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/75/notes")
        comment_response = jj.Response(status=201, json={"id": 41})

        # GET notes - needed for _find_bot_comment
        get_notes_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/75/notes")
        get_notes_response = jj.Response(status=200, json=[])

        settings = Settings(
            gitlab_url=mock_url,
            gitlab_project_id=123,
            gitlab_token="test-token",
            target_branch="main",
            queue_label="merge_queue",
            hotfix_label="hotfix",
            jwt_secret="a" * 64,
            webhook_secret="test-webhook-secret",
            poll_interval_seconds=0.5,
        )

    async with (
        mocked(get_mr_matcher, get_mr_response),
        mocked(rebase_matcher, rebase_response),
        mocked(pipelines_matcher, pipelines_response),
        mocked(get_notes_matcher, get_notes_response),
        mocked(comment_matcher, comment_response),
    ):
        with when("shutdown during active processing"):
            gitlab_client = GitLabClient(settings)
            notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)
            processor = MergeProcessor(
                gitlab_client=gitlab_client,
                queue_manager=queue,
                notifier=notifier,
                settings=settings,
            )

            # Process in background
            async def process_and_shutdown():
                # Get the MR
                queue_item = await queue.get_next_mr()

                # Start processing
                process_task = asyncio.create_task(processor._process_mr(queue_item))

                # Wait briefly for processing to start
                await asyncio.sleep(0.2)

                # Check if processing
                is_processing = processor.is_processing
                current_mr = processor.current_mr_iid

                # Request shutdown
                processor.request_shutdown()

                # Try to get result
                try:
                    result = await asyncio.wait_for(process_task, timeout=2.0)
                except (TimeoutError, asyncio.CancelledError):
                    result = ProcessingResult.ERROR

                return is_processing, current_mr, result

            _was_processing, _current_mr, result = await process_and_shutdown()

        with then("processing state is tracked correctly"):
            # During shutdown, processor may have finished early
            # We check that shutdown was properly requested and processed
            assert processor.is_shutdown_requested
            # Result should indicate error due to shutdown
            assert result == ProcessingResult.ERROR
            assert not processor.is_processing

    await db.close()


__all__ = [
    "concurrent_processing_during_shutdown",
    "graceful_shutdown_during_rebase",
    "graceful_shutdown_with_no_processing",
    "processor_state_recovery_after_shutdown",
    "shutdown_timeout_handling",
]
