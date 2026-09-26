"""Test resume from rebasing goes straight to testing when the MR is up-to-date.

After a restart in the rebasing state, the rebase may already have finished.
The MR then reports zero diverged commits, so its SHA will not change any
more: the existing pipeline is used right away instead of polling the rebase
and waiting for a SHA change that will never come.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import FakeCurrentState, FakeStateMachine, create_mr, create_pipeline

from .._helpers import create_mock_processor, create_processing_context, create_test_queue_item, instant_poll


class Scenario(vedro.Scenario):
    subject = "resume from rebasing goes straight to testing when MR is up-to-date"

    def given_processor_resuming_after_rebase_finished(self):
        self.processor = create_mock_processor(poll_fn=instant_poll)
        self.gitlab_client = self.processor.gitlab_client
        self.gitlab_client.mr_responses[42] = create_mr(iid=42, sha="rebased123", diverged_commits_count=0)
        self.gitlab_client.latest_pipeline_response = create_pipeline(id=200, sha="rebased123", status="success")
        self.processor.queue_manager.add_item(create_test_queue_item(mr_iid=42, state="rebasing"))

        self.sm = FakeStateMachine(current_state=FakeCurrentState(id="rebasing"))
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_execute_workflow_is_called(self):
        self.result = await self.processor._execute_workflow(self.ctx)

    def then_workflow_succeeds(self):
        assert self.result == ProcessingResult.SUCCESS

    def and_rebase_status_was_not_polled(self):
        assert self.gitlab_client.check_rebase_status_calls == []

    def and_testing_started_with_current_pipeline(self):
        assert self.sm.rebase_complete_calls[0]["pipeline_id"] == 200
        assert self.sm.rebase_complete_calls[0]["expected_sha"] == "rebased123"
