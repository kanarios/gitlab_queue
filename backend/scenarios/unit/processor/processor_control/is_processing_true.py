"""Test is_processing property returns True when _current_mr_iid is set.

Line 1555: is_processing returns True when _current_mr_iid is not None.
"""

from __future__ import annotations

import vedro

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "is_processing returns True when processing an MR"

    def given_processor_with_active_mr(self):
        self.processor = create_mock_processor()
        self.processor._current_mr_iid = 42

    def when_is_processing_is_checked(self):
        self.result = self.processor.is_processing

    def then_result_is_true(self):
        assert self.result is True
