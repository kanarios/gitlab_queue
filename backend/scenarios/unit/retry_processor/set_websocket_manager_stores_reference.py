"""Test set_websocket_manager stores the provided manager on the processor."""

from __future__ import annotations

from unittest.mock import MagicMock

import vedro

from ._helpers import create_test_retry_processor


class Scenario(vedro.Scenario):
    subject = "set_websocket_manager stores the manager reference"

    def given_processor_and_websocket_manager(self):
        self.processor = create_test_retry_processor()
        self.mock_manager = MagicMock()

    def when_set_websocket_manager_is_called(self):
        self.processor.set_websocket_manager(self.mock_manager)

    def then_websocket_manager_is_stored(self):
        assert self.processor.websocket_manager is self.mock_manager
