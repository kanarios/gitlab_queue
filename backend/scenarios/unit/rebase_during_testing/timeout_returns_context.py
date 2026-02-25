"""Test scenario: timeout during pipeline wait returns None pipeline."""

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
    # Set very short timeout to simulate timeout scenario
    settings.post_rebase_pipeline_wait_seconds = 0
    return settings


def create_mock_gitlab_client_timeout() -> MagicMock:
    """Create mock GitLabClient that simulates pipeline wait timeout."""
    client = MagicMock()

    # check_needs_rebase: needs rebase
    mr_needs_rebase = MagicMock()
    mr_needs_rebase.has_conflicts = False
    mr_needs_rebase.merge_status = "cannot_be_merged"
    mr_needs_rebase.sha = "old_sha_123"
    mr_needs_rebase.rebase_in_progress = False

    # After cancel/rebase
    mr_after_rebase = MagicMock()
    mr_after_rebase.has_conflicts = False
    mr_after_rebase.merge_status = "can_be_merged"
    mr_after_rebase.sha = "new_sha_456"
    mr_after_rebase.rebase_in_progress = False

    client.get_mr = AsyncMock(side_effect=[mr_needs_rebase, mr_needs_rebase, mr_after_rebase, mr_after_rebase])
    client.cancel_pipeline = AsyncMock()
    client.rebase_mr = AsyncMock()
    client.check_rebase_status = AsyncMock(return_value=(False, False))

    # No valid pipeline found after timeout - return pipeline with wrong SHA
    stale_pipeline = MagicMock()
    stale_pipeline.id = 100  # Same as old pipeline
    stale_pipeline.sha = "old_sha_123"
    stale_pipeline.status = "canceled"
    client.get_latest_mr_pipeline = AsyncMock(return_value=stale_pipeline)

    return client


class Scenario(vedro.Scenario):
    subject = "timeout waiting for new pipeline returns none and updated context"

    def given_handler_that_will_timeout_on_pipeline_wait(self):
        self.gitlab_client = create_mock_gitlab_client_timeout()
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

    def then_new_pipeline_should_be_none(self):
        assert self.new_pipeline is None

    def and_rebase_count_should_be_incremented(self):
        assert self.new_ctx.rebase_count == 1

    def and_current_pipeline_id_should_be_none(self):
        assert self.new_ctx.current_pipeline_id is None

    def and_rebase_should_have_been_attempted(self):
        self.gitlab_client.rebase_mr.assert_awaited_once_with(42)
