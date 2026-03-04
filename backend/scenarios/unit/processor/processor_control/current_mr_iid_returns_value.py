"""Test current_mr_iid property returns the current MR IID.

Line 1560: current_mr_iid property returns _current_mr_iid value.
"""

from __future__ import annotations

import vedro

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "current_mr_iid returns the active MR IID"

    def given_processor_with_active_mr(self):
        self.processor = create_mock_processor()
        self.processor._current_mr_iid = 99

    def when_current_mr_iid_is_accessed(self):
        self.result = self.processor.current_mr_iid

    def then_result_equals_active_mr_iid(self):
        assert self.result == 99
