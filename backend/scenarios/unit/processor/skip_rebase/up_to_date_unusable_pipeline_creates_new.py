"""Test process_rebase creates a pipeline when an up-to-date MR has no usable one.

Skipping the rebase means nothing is pushed, so GitLab will not start a
pipeline on its own. A failed/canceled pipeline, a pipeline on another SHA,
a pipeline that cannot finish on its own (canceling, manual, skipped),
or no pipeline at all must be replaced by a freshly created one.
"""

from __future__ import annotations

import vedro
from vedro import params

from gitlab_queue.core.types import ProcessingResult
from scenarios.fakes import FakeGitLabClient, create_mr, create_pipeline

from .._helpers import create_mock_state_machine, create_processing_context, create_test_rebase_handler


class Scenario(vedro.Scenario):
    subject = "up-to-date MR creates new pipeline when latest is {case}"

    @params("failed", create_pipeline(id=500, sha="abc123", status="failed"))
    @params("canceled", create_pipeline(id=500, sha="abc123", status="canceled"))
    @params("canceling", create_pipeline(id=500, sha="abc123", status="canceling"))
    @params("manual", create_pipeline(id=500, sha="abc123", status="manual"))
    @params("skipped", create_pipeline(id=500, sha="abc123", status="skipped"))
    @params("on another sha", create_pipeline(id=500, sha="old999", status="success"))
    @params("missing", None)
    def __init__(self, case: str, latest_pipeline):
        self.case = case
        self.latest_pipeline = latest_pipeline

    def given_up_to_date_mr_without_usable_pipeline(self):
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha="abc123", source_branch="my-feature", diverged_commits_count=0)},
            latest_pipeline_response=self.latest_pipeline,
            created_pipeline=create_pipeline(id=600, sha="abc123", status="pending"),
        )
        self.handler = create_test_rebase_handler(gitlab_client=self.gitlab_client)
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_process_rebase_is_called(self):
        self.result = await self.handler.process_rebase(self.ctx)

    def then_result_is_success(self):
        assert self.result == ProcessingResult.SUCCESS

    def and_rebase_was_not_called(self):
        assert self.gitlab_client.rebase_calls == []

    def and_pipeline_was_created_for_source_branch(self):
        assert self.gitlab_client.create_pipeline_calls == ["my-feature"]

    def and_testing_started_with_created_pipeline(self):
        call = self.sm.rebase_complete_calls[0]
        assert call["pipeline_id"] == 600
        assert call["expected_sha"] == "abc123"
