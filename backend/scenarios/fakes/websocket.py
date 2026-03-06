from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(eq=False)
class FakeWebSocket:
    """Fake WebSocket connection for testing WebSocketManager broadcasts.

    Simulates a Starlette WebSocket with send_json recording and
    configurable error injection.
    """

    send_json_calls: list[dict[str, Any]] = field(default_factory=list)
    send_error: Exception | None = None

    class _ClientState:
        name = "CONNECTED"

    client_state: Any = field(default_factory=_ClientState)

    async def send_json(self, data: dict[str, Any]) -> None:
        if self.send_error is not None:
            raise self.send_error
        self.send_json_calls.append(data)

    @property
    def last_sent(self) -> dict[str, Any] | None:
        return self.send_json_calls[-1] if self.send_json_calls else None

    @property
    def send_count(self) -> int:
        return len(self.send_json_calls)


@dataclass
class FakeWebSocketManager:
    broadcast_calls: list[dict[str, Any]] = field(default_factory=list)

    async def broadcast(self, message: dict[str, Any]) -> None:
        self.broadcast_calls.append(message)

    async def broadcast_queue_updated(self, queue: list[dict[str, Any]], stats: dict[str, Any]) -> None:
        self.broadcast_calls.append(
            {
                "type": "queue_updated",
                "queue": queue,
                "stats": stats,
            }
        )

    async def broadcast_mr_status_changed(self, mr_iid: int, old_status: str, new_status: str) -> None:
        self.broadcast_calls.append(
            {
                "type": "mr_status_changed",
                "mr_iid": mr_iid,
                "old_status": old_status,
                "new_status": new_status,
            }
        )

    async def broadcast_mr_completed(
        self,
        mr_iid: int,
        status: str,
        finished_at: Any = None,
        failure_reason: str | None = None,
    ) -> None:
        self.broadcast_calls.append(
            {
                "type": "mr_completed",
                "mr_iid": mr_iid,
                "status": status,
                "finished_at": finished_at,
                "failure_reason": failure_reason,
            }
        )
