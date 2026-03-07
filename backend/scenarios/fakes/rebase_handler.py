from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeRebaseDuringTestingHandler:
    """Fake for RebaseDuringTestingHandler used in processor tests.

    Configure ``result`` for successful rebase or ``error`` for failure injection.
    Records all calls to ``handle_rebase_if_needed``.
    """

    result: Any = None
    error: Exception | None = None
    gitlab_client: Any = None

    calls: list[dict[str, Any]] = field(default_factory=list)

    async def handle_rebase_if_needed(
        self,
        mr_iid: int,
        ctx: Any,
    ) -> Any:
        self.calls.append(
            {
                "mr_iid": mr_iid,
                "ctx": ctx,
            }
        )
        if self.error is not None:
            raise self.error
        return self.result
