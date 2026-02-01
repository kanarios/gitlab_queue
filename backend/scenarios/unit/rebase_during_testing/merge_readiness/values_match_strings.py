"""Test MergeReadiness enum values match expected strings."""

import vedro
from vedro import params

from gitlab_queue.core.rebase_during_testing import MergeReadiness


class Scenario(vedro.Scenario):
    subject = "MergeReadiness.{member_name} has value '{expected}'"

    @params("READY", "ready")
    @params("NEEDS_REBASE", "needs_rebase")
    @params("HAS_CONFLICTS", "has_conflicts")
    def __init__(self, member_name: str, expected: str):
        self.member_name = member_name
        self.expected = expected

    def given_merge_readiness_enum(self):
        self.status = getattr(MergeReadiness, self.member_name)

    def when_value_is_accessed(self):
        self.actual_value = self.status.value

    def then_value_matches_expected(self):
        assert self.actual_value == self.expected
