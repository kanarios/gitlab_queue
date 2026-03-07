from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeHandler:
    handle_calls: list[Any] = field(default_factory=list)
    handle_error: Exception | None = None

    async def handle(self, event: Any) -> None:
        self.handle_calls.append(event)
        if self.handle_error:
            raise self.handle_error


@dataclass
class FakeHandlerFactory:
    handler: FakeHandler = field(default_factory=FakeHandler)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, **kwargs: Any) -> FakeHandler:
        self.calls.append(kwargs)
        return self.handler
