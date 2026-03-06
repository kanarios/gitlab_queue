"""Test check_and_handle_rebase_during_testing returns CONFLICT on GitLabConflictError.

When handle_rebase_if_needed raises GitLabConflictError because the rebase
encountered merge conflicts, the handler should trigger_rebase_failed and
return ProcessingResult.CONFLICT.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabConflictError
from gitlab_queue.core.processor import ProcessingResult
from gitlab_queue.core.rebase_coordinator import check_and_handle_rebase_during_testing
from scenarios.fakes import FakeGitLabClient, FakeRebaseDuringTestingHandler

from .._helpers import (
    create_mock_pipeline,
    create_mock_state_machine,
    create_pipeline_wait_state,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "rebase during testing returns conflict on conflict error"

    def given_processor_with_rebase_conflict_during_testing(self):
        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.rebase_handler = FakeRebaseDuringTestingHandler(
            error=GitLabConflictError("MR has conflicts during testing"),
        )

        self.gitlab_client = FakeGitLabClient()
        self.gitlab_client.mr_conflicts = ["file1.py"]

        self.state = create_pipeline_wait_state(rebase_handler=self.rebase_handler)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

    async def when_check_and_handle_rebase_during_testing_is_called(self):
        self.result = await check_and_handle_rebase_during_testing(
            gitlab_client=self.gitlab_client,
            ctx=self.ctx,
            state=self.state,
            pipeline=self.pipeline,
        )

    def then_result_is_conflict(self):
        assert self.result == ProcessingResult.CONFLICT

    def and_trigger_conflict_during_testing_was_called(self):
        assert len(self.mock_sm.conflict_during_testing_calls) == 1
