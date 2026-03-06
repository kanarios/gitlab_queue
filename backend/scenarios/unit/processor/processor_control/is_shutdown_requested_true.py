"""Test is_shutdown_requested property returns True after request_shutdown().

is_shutdown_requested reflects the internal _shutdown_event state
and becomes True after calling request_shutdown().
"""

from __future__ import annotations

import vedro

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "is_shutdown_requested returns True after requesting shutdown"

    def given_processor_with_shutdown_set(self):
        self.processor = create_mock_processor()
        self.processor.request_shutdown()

    def when_is_shutdown_requested_is_checked(self):
        self.result = self.processor.is_shutdown_requested

    def then_result_is_true(self):
        assert self.result is True
