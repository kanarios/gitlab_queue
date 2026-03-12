"""Test should_skip_stale_pipeline switches to newer pipeline with matching SHA.

When GitLab creates a new pipeline on the same commit after rebase,
the bot should switch to tracking the newer pipeline instead of skipping it.
This prevents MR from getting stuck in 'testing' state indefinitely.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "should skip stale pipeline switches to newer pipeline with matching SHA"

    def given_processor_with_newer_pipeline_matching_sha(self):
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(
            mr_iid=42,
            state="testing",
            pipeline_id=100,
            expected_sha="abc12345",
        )
        self.processor.queue_manager.add_item(self.queue_item)

        self.pipeline = create_mock_pipeline(
            pipeline_id=200,
            sha="abc12345",
            status="running",
        )

    async def when_should_skip_stale_pipeline_is_called(self):
        self.result = await self.processor._pipeline_handler.should_skip_stale_pipeline(
            42,
            self.pipeline,
        )

    def then_pipeline_should_not_be_skipped(self):
        assert self.result is False

    def then_update_state_was_called_with_new_pipeline_id(self):
        calls = self.processor.queue_manager.update_state_calls
        assert len(calls) == 1
        assert calls[0]["mr_iid"] == 42
        assert calls[0]["pipeline_id"] == 200
