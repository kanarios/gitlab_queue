"""Test resume from rebasing starts a rebase when none is running.

After a restart in the rebasing state the MR may still be behind its target
with no rebase running: the rebase was never started, or the target moved on
after it finished. Waiting for a SHA change would time out and send an MR
that is behind target to testing, so a new rebase is started instead.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import FakeCurrentState, FakeStateMachine, create_mr, create_pipeline

from .._helpers import create_mock_processor, create_processing_context, create_test_queue_item, instant_poll


class Scenario(vedro.Scenario):
    subject = "resume from rebasing starts a rebase when MR is behind and none is running"

    def given_processor_resuming_mr_behind_target(self):
        self.processor = create_mock_processor(poll_fn=instant_poll)
        self.gitlab_client = self.processor.gitlab_client
        self.gitlab_client.mr_response_sequence = [
            create_mr(iid=42, sha="old_sha", diverged_commits_count=3),
        ]
        self.gitlab_client.mr_responses[42] = create_mr(iid=42, sha="new_sha")
        self.gitlab_client.rebase_status = (False, False)
        self.gitlab_client.latest_pipeline_response = create_pipeline(id=200, sha="new_sha", status="success")
        self.processor.queue_manager.add_item(create_test_queue_item(mr_iid=42, state="rebasing"))

        self.sm = FakeStateMachine(current_state=FakeCurrentState(id="rebasing"))
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_execute_workflow_is_called(self):
        self.result = await self.processor._execute_workflow(self.ctx)

    def then_workflow_succeeds(self):
        assert self.result == ProcessingResult.SUCCESS

    def and_rebase_was_started(self):
        assert self.gitlab_client.rebase_calls == [42]

    def and_testing_started_on_rebased_sha(self):
        assert self.sm.rebase_complete_calls[0]["pipeline_id"] == 200
        assert self.sm.rebase_complete_calls[0]["expected_sha"] == "new_sha"
