"""Test scenario: old pipeline is cancelled when rebase starts."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.core.rebase_during_testing import (
    RebaseDuringTestingContext,
    RebaseDuringTestingHandler,
)


def create_mock_settings() -> MagicMock:
    """
    Create a MagicMock configured with settings used by rebase handler tests.

    Returns:
        MagicMock: A mock settings object with attributes:
            - rebase_timeout_seconds = 60
            - pipeline_poll_interval_seconds = 5
            - post_rebase_pipeline_wait_seconds = 60
    """
    settings = MagicMock()
    settings.rebase_timeout_seconds = 60
    settings.pipeline_poll_interval_seconds = 5
    settings.post_rebase_pipeline_wait_seconds = 60
    return settings


def create_mock_gitlab_client_needs_rebase() -> MagicMock:
    """
    Create a MagicMock GitLab client configured to simulate a merge request that requires a rebase and the subsequent rebase flow.

    The mock's get_mr call yields, in order:
      1. an MR that needs rebase (sha="old_sha_123", merge_status="cannot_be_merged"),
      2. the same MR after cancellation (sha="old_sha_123"),
      3. and 4. an MR after rebase (sha="new_sha_456", merge_status="can_be_merged").

    Also configures:
      - cancel_pipeline: AsyncMock to observe cancellation calls,
      - rebase_mr: AsyncMock to observe rebase initiation,
      - check_rebase_status: AsyncMock returning (False, False),
      - get_latest_mr_pipeline: AsyncMock returning a new pipeline MagicMock with id=200, sha="new_sha_456", status="running".

    Returns:
        MagicMock: A mocked GitLab client with the above AsyncMock methods and staged get_mr responses.
    """
    client = MagicMock()

    # First call to get_mr for check_needs_rebase: needs rebase
    mr_needs_rebase = MagicMock()
    mr_needs_rebase.has_conflicts = False
    mr_needs_rebase.merge_status = "cannot_be_merged"
    mr_needs_rebase.sha = "old_sha_123"
    mr_needs_rebase.rebase_in_progress = False

    # Second call to get_mr after cancel: capture old SHA
    mr_after_cancel = MagicMock()
    mr_after_cancel.has_conflicts = False
    mr_after_cancel.merge_status = "cannot_be_merged"
    mr_after_cancel.sha = "old_sha_123"
    mr_after_cancel.rebase_in_progress = False

    # Third call after rebase for wait check
    mr_rebased = MagicMock()
    mr_rebased.has_conflicts = False
    mr_rebased.merge_status = "can_be_merged"
    mr_rebased.sha = "new_sha_456"
    mr_rebased.rebase_in_progress = False

    client.get_mr = AsyncMock(side_effect=[mr_needs_rebase, mr_after_cancel, mr_rebased, mr_rebased])
    client.cancel_pipeline = AsyncMock()
    client.rebase_mr = AsyncMock()
    client.check_rebase_status = AsyncMock(return_value=(False, False))

    # Pipeline after rebase
    new_pipeline = MagicMock()
    new_pipeline.id = 200
    new_pipeline.sha = "new_sha_456"
    new_pipeline.status = "running"
    client.get_latest_mr_pipeline = AsyncMock(return_value=new_pipeline)

    return client


class Scenario(vedro.Scenario):
    subject = "old pipeline is cancelled when rebase during testing starts"

    def given_handler_with_mr_needing_rebase(self):
        """
        Prepare a RebaseDuringTestingHandler with a mocked GitLab client and settings, and initialize a RebaseDuringTestingContext that simulates an MR requiring a rebase.

        The created context has rebase_count=0, max_attempts=3, and current_pipeline_id=100.
        """
        self.gitlab_client = create_mock_gitlab_client_needs_rebase()
        self.settings = create_mock_settings()
        self.handler = RebaseDuringTestingHandler(
            gitlab_client=self.gitlab_client,
            settings=self.settings,
        )
        self.ctx = RebaseDuringTestingContext(
            rebase_count=0,
            max_attempts=3,
            current_pipeline_id=100,
        )

    async def when_handle_rebase_if_needed_is_called(self):
        """
        Invokes the handler's rebase check for merge request 42 and stores the resulting context and pipeline on the test instance.

        The coroutine calls handle_rebase_if_needed(42, self.ctx) and assigns its returned (context, pipeline) tuple to self.new_ctx and self.new_pipeline respectively.
        """
        self.new_ctx, self.new_pipeline = await self.handler.handle_rebase_if_needed(42, self.ctx)

    def then_old_pipeline_should_be_cancelled(self):
        """
        Asserts that the original pipeline was cancelled.

        Verifies the GitLab client's cancel_pipeline was awaited exactly once with the initial pipeline id 100.
        """
        self.gitlab_client.cancel_pipeline.assert_awaited_once_with(100)

    def and_rebase_should_have_been_initiated(self):
        """
        Asserts that a rebase was initiated for the merge request with ID 42.

        Raises:
            AssertionError: If the GitLab client's `rebase_mr` was not awaited exactly once with `42`.
        """
        self.gitlab_client.rebase_mr.assert_awaited_once_with(42)

    def and_new_pipeline_should_be_returned(self):
        """
        Asserts that a new pipeline was returned and its id equals 200.

        This verifies the handler produced a pipeline and that its identifier matches the expected scenario value.
        """
        assert self.new_pipeline is not None
        assert self.new_pipeline.id == 200

    def and_rebase_count_should_be_incremented(self):
        """
        Asserts that the rebase count in the updated context has been incremented to 1.

        Raises:
            AssertionError: If `self.new_ctx.rebase_count` is not equal to 1.
        """
        assert self.new_ctx.rebase_count == 1
