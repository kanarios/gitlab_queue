"""Test request_shutdown sets shutdown flag."""

from __future__ import annotations

import vedro

from ._helpers import create_test_retry_processor


class Scenario(vedro.Scenario):
    subject = "request_shutdown sets is_shutdown_requested to True"

    def given_processor(self):
        self.processor = create_test_retry_processor()

    def when_request_shutdown_is_called(self):
        self.processor.request_shutdown()

    def then_is_shutdown_requested_is_true(self):
        assert self.processor.is_shutdown_requested is True
