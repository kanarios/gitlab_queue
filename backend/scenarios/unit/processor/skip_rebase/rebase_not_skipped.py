"""Test process_rebase still rebases unless the MR is provably up-to-date.

Only an explicit zero divergence skips the rebase, and only when no other
signal contradicts it: GitLab also reports 0 when it cannot resolve a
branch SHA, and older GitLab versions omit the field entirely (None).
"""

from __future__ import annotations

import vedro
from vedro import params

from scenarios.fakes import FakeGitLabClient, create_mr, create_pipeline

from .._helpers import create_mock_state_machine, create_processing_context, create_test_rebase_handler


class Scenario(vedro.Scenario):
    subject = "rebase is not skipped when {case}"

    @params("MR is behind target", {"diverged_commits_count": 2})
    @params("divergence is unknown", {"diverged_commits_count": None})
    @params("MR has conflicts", {"diverged_commits_count": 0, "has_conflicts": True})
    @params("GitLab says need_rebase", {"diverged_commits_count": 0, "detailed_merge_status": "need_rebase"})
    @params("SHA is empty", {"diverged_commits_count": 0, "sha": ""})
    def __init__(self, case: str, mr_fields: dict):
        self.case = case
        self.mr_fields = mr_fields

    def given_mr_that_is_not_provably_up_to_date(self):
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, **{"sha": "abc123", **self.mr_fields})},
            latest_pipeline_response=create_pipeline(id=500, sha="abc123", status="success"),
            rebase_status=(True, False, None),  # keep rebase "in progress" so polling stops early
        )
        self.handler = create_test_rebase_handler(gitlab_client=self.gitlab_client)
        self.ctx = create_processing_context(mr_iid=42, state_machine=create_mock_state_machine())

    async def when_process_rebase_is_called(self):
        await self.handler.process_rebase(self.ctx)

    def then_rebase_was_called(self):
        assert self.gitlab_client.rebase_calls == [42]

    def and_no_pipeline_was_created(self):
        assert self.gitlab_client.create_pipeline_calls == []
