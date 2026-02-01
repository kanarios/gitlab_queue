"""Test RebaseDuringTestingContext default values."""

import vedro
from vedro import params

from gitlab_queue.core.rebase_during_testing import RebaseDuringTestingContext


class Scenario(vedro.Scenario):
    subject = "RebaseDuringTestingContext default {field}={expected}"

    @params("rebase_count", 0)
    @params("max_attempts", 3)
    @params("current_pipeline_id", None)
    def __init__(self, field: str, expected: object):
        self.field = field
        self.expected = expected

    def given_context_with_defaults(self):
        self.ctx = RebaseDuringTestingContext()

    def then_field_has_default_value(self):
        assert getattr(self.ctx, self.field) == self.expected
