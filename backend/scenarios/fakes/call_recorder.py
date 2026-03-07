"""CallRecorder: typed call tracking for test doubles.

Provides .call_count, .call_args, .call_args_list, and assert_* methods
so that existing test assertions continue to work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CallArgs:
    """Immutable record of a single call's positional and keyword arguments."""

    args: tuple[Any, ...]
    kwargs: dict[str, Any]

    def __getitem__(self, index: int) -> Any:
        if index == 0:
            return self.args
        if index == 1:
            return self.kwargs
        raise IndexError(index)


class CallRecorder:
    """Records async calls and exposes an API compatible with common Mock assertions."""

    def __init__(self) -> None:
        self._calls: list[CallArgs] = []

    # --- async callable ---------------------------------------------------

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self._calls.append(CallArgs(args=args, kwargs=kwargs))
        return self._return_value(*args, **kwargs)

    def _return_value(self, *args: Any, **kwargs: Any) -> Any:
        """Override in subclass to control the return value."""
        return None

    # --- properties --------------------------------------------------------

    @property
    def call_count(self) -> int:
        return len(self._calls)

    @property
    def call_args(self) -> CallArgs | None:
        """Most recent call, or None if not called."""
        return self._calls[-1] if self._calls else None

    @property
    def call_args_list(self) -> list[CallArgs]:
        return list(self._calls)

    # --- assertions --------------------------------------------------------

    def assert_not_called(self) -> None:
        assert self.call_count == 0, f"Expected no calls, but was called {self.call_count} time(s)"

    def assert_not_awaited(self) -> None:
        self.assert_not_called()

    def assert_awaited_once(self) -> None:
        assert self.call_count == 1, f"Expected exactly 1 call, but was called {self.call_count} time(s)"

    def assert_awaited_once_with(self, *args: Any, **kwargs: Any) -> None:
        self.assert_awaited_once()
        actual = self._calls[0]
        assert actual.args == args and actual.kwargs == kwargs, (
            f"Expected call with args={args}, kwargs={kwargs}, got args={actual.args}, kwargs={actual.kwargs}"
        )
