from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeOutcome:
    _exception: BaseException | None = None
    failed: bool = False

    def exception(self) -> BaseException | None:
        return self._exception


@dataclass
class FakeNextAction:
    sleep: float = 0.0


@dataclass
class FakeRetryCallState:
    outcome: FakeOutcome | None = field(default=None)
    attempt_number: int = 1
    seconds_since_start: float = 0.0
    next_action: FakeNextAction | None = field(default=None)
