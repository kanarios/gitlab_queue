"""Test set_websocket_manager() assigns the manager to _websocket_manager.

set_websocket_manager() stores the given WebSocketManager instance
on the _websocket_manager attribute.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import vedro

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "set_websocket_manager assigns the manager"

    def given_processor_and_manager(self):
        self.processor = create_mock_processor()
        self.manager = MagicMock()

    def when_set_websocket_manager_is_called(self):
        self.processor.set_websocket_manager(self.manager)

    def then_websocket_manager_is_assigned(self):
        assert self.processor._websocket_manager is self.manager
