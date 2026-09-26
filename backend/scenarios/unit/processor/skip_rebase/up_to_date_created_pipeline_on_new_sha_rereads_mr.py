"""Test skip path re-reads the MR when the created pipeline runs on a newer SHA.

If someone pushes to the source branch between reading the MR and creating
the pipeline, the new pipeline runs on the new HEAD. Entering testing with
the old SHA as expected_sha would make the testing phase skip that pipeline
as stale, so the handler re-reads the MR and uses its current SHA instead.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.types import ProcessingResult
from scenarios.fakes import FakeGitLabClient, create_mr, create_pipeline

from .._helpers import create_mock_state_machine, create_processing_context, create_test_rebase_handler, exhaustive_poll


class Scenario(vedro.Scenario):
    subject = "skip path re-reads MR when created pipeline is on a newer SHA"

    def given_up_to_date_mr_pushed_during_pipeline_creation(self):
        new_pipeline = create_pipeline(id=600, sha="new456", status="pending")
        self.gitlab_client = FakeGitLabClient(
            mr_response_sequence=[
                create_mr(iid=42, sha="abc123", diverged_commits_count=0),  # pre-rebase capture
                create_mr(iid=42, sha="new456"),  # re-read after SHA mismatch
            ],
            latest_pipeline_sequence=[None, new_pipeline],
            created_pipeline=new_pipeline,
        )
        self.handler = create_test_rebase_handler(gitlab_client=self.gitlab_client, poll_fn=exhaustive_poll)
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_process_rebase_is_called(self):
        self.result = await self.handler.process_rebase(self.ctx)

    def then_result_is_success(self):
        assert self.result == ProcessingResult.SUCCESS

    def and_only_one_pipeline_was_created(self):
        assert len(self.gitlab_client.create_pipeline_calls) == 1

    def and_testing_expects_the_new_sha(self):
        call = self.sm.rebase_complete_calls[0]
        assert call["pipeline_id"] == 600
        assert call["expected_sha"] == "new456"
