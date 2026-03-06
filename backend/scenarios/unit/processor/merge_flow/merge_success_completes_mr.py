"""Test _process_merge triggers merge_success and returns SUCCESS on successful merge.

When gitlab_client.merge_mr completes successfully, the processor should
trigger the merge_success transition on the state machine and return
ProcessingResult.SUCCESS.

Covers lines 1164-1166 in _process_merge: the happy-path branch after
asyncio.wait_for completes, calling trigger_merge_success.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import create_mr

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "process merge triggers merge success and returns SUCCESS on successful merge"

    def given_processor_with_successful_merge(self):
        """
        Set up test fixtures for a successful merge scenario.

        Creates a mock processor, a queue item with an expected SHA, configures the processor's queue manager to return that item, stubs the GitLab client's merge_mr to return a merged MR, and prepares a mock state machine and processing context for mr_iid 42.
        """
        self.processor = create_mock_processor()

        # Queue item with an expected SHA to test the race-condition guard
        self.queue_item = create_test_queue_item(mr_iid=42, state="merging", expected_sha="sha_merge_ok")
        self.processor.queue_manager.add_item(self.queue_item)

        # Simulate a merged MR returned by merge_mr
        self.merged_mr = create_mr(iid=42, state="merged")
        self.processor.gitlab_client.merge_result = self.merged_mr

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_process_merge_is_called(self):
        """
        Call the processor's _process_merge with the prepared context and store its result on self.result.

        The awaited ProcessingResult returned by _process_merge is saved to the instance attribute `self.result` for later assertions.
        """
        self.result = await self.processor._process_merge(self.ctx)

    def then_result_is_success(self):
        """
        Assert that the processing result equals ProcessingResult.SUCCESS.

        Verifies the processor reported a successful merge by checking the stored result.
        """
        assert self.result == ProcessingResult.SUCCESS

    def and_merge_success_is_triggered_on_state_machine(self):
        """
        Assert that the state machine's merge-success transition was awaited exactly once.

        Verifies the processor triggered the merge success transition on the mocked state machine.
        """
        assert len(self.mock_sm.merge_success_calls) == 1

    def and_merge_mr_is_called_with_correct_sha(self):
        """
        Asserts the GitLab client's merge_mr was called once with the expected MR IID and expected SHA.
        """
        assert len(self.processor.gitlab_client.merge_calls) == 1
        assert self.processor.gitlab_client.merge_calls[0] == (42, "sha_merge_ok")

    def and_no_failure_transitions_are_triggered(self):
        """
        Asserts that no failure or timeout transitions were triggered on the mock state machine.
        """
        assert self.mock_sm.merge_failed_calls == []
        assert self.mock_sm.timeout_calls == []
