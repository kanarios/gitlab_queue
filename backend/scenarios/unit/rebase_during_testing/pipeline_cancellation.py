"""Test scenario: old pipeline is cancelled when rebase starts."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.core.rebase_during_testing import (
    RebaseDuringTestingContext,
    RebaseDuringTestingHandler,
)


def create_mock_settings() -> MagicMock:
    """Create mock Settings for rebase handler tests."""
    settings = MagicMock()
    settings.rebase_timeout_seconds = 60
    settings.pipeline_poll_interval_seconds = 5
    settings.post_rebase_pipeline_wait_seconds = 60
    return settings


def create_mock_gitlab_client_needs_rebase() -> MagicMock:
    """Create mock GitLabClient that indicates MR needs rebase."""
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
        self.new_ctx, self.new_pipeline = await self.handler.handle_rebase_if_needed(42, self.ctx)

    def then_old_pipeline_should_be_cancelled(self):
        self.gitlab_client.cancel_pipeline.assert_called_once_with(100)

    def and_rebase_should_have_been_initiated(self):
        self.gitlab_client.rebase_mr.assert_called_once_with(42)

    def and_new_pipeline_should_be_returned(self):
        assert self.new_pipeline is not None, "Expected new pipeline after rebase"
        assert self.new_pipeline.id == 200, f"Expected new pipeline id=200, got {self.new_pipeline.id}"

    def and_rebase_count_should_be_incremented(self):
        assert self.new_ctx.rebase_count == 1, f"Expected rebase_count=1, got {self.new_ctx.rebase_count}"
