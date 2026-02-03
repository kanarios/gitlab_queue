"""Test is_processing property returns False when no items are being processed."""

from __future__ import annotations

import vedro

from ._helpers import create_test_retry_processor


class Scenario(vedro.Scenario):
    subject = "is_processing returns False when processor is idle"

    def given_idle_processor(self):
        self.processor = create_test_retry_processor()

    def when_is_processing_is_read(self):
        self.result = self.processor.is_processing

    def then_result_is_false(self):
        assert self.result is False
