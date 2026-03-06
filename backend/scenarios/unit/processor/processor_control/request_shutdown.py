"""Test request_shutdown() sets the shutdown event.

Lines 1531-1532: request_shutdown() calls _shutdown_event.set().
"""

from __future__ import annotations

import vedro

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "request_shutdown sets the shutdown event"

    def given_processor(self):
        self.processor = create_mock_processor()

    def when_request_shutdown_is_called(self):
        self.processor.request_shutdown()

    def then_shutdown_event_is_set(self):
        assert self.processor._shutdown_event.is_set()
