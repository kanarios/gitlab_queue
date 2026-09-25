"""Project-scoped broadcasts must not reach another project's clients."""

from __future__ import annotations

import vedro
from scenarios.fakes.websocket import FakeWebSocket

from gitlab_queue.api.websocket import WebSocketManager


class Scenario(vedro.Scenario):
    subject = "WebSocketManager isolates broadcasts by project"

    def given_clients_for_two_projects(self):
        self.manager = WebSocketManager()
        self.first = FakeWebSocket()
        self.second = FakeWebSocket()
        self.manager._connections.update((self.first, self.second))
        self.manager._project_connections = {101: {self.first}, 202: {self.second}}

    async def when_first_project_is_broadcast(self):
        await self.manager.broadcast_queue_updated([], {"total": 0}, project_id=101)

    def then_only_first_project_client_receives_the_event(self):
        assert self.first.send_count == 1
        assert self.first.last_sent is not None
        assert self.first.last_sent["data"]["project_id"] == 101
        assert self.second.send_count == 0
