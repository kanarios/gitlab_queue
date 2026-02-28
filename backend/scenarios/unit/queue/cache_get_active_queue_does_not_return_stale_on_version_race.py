"""BUG: get_active_queue() returns stale items on version race."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import vedro

from gitlab_queue.core.queue import QueueManager


class _FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> _FakeResult:
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class _FakeSession:
    def __init__(self, *, rows: list[dict[str, Any]], on_execute: callable[[], None]) -> None:
        self._rows = rows
        self._on_execute = on_execute

    async def execute(self, *_args: Any, **_kwargs: Any) -> _FakeResult:
        # Simulate another concurrent refresh that invalidates + updates cache
        # between version capture and this call's set_active_queue().
        self._on_execute()
        return _FakeResult(self._rows)

    async def commit(self) -> None:
        return None


class _FakeDB:
    def __init__(self, *, rows: list[dict[str, Any]], on_execute: callable[[], None]) -> None:
        self._rows = rows
        self._on_execute = on_execute

    @asynccontextmanager
    async def session(self):
        yield _FakeSession(rows=self._rows, on_execute=self._on_execute)


class Scenario(vedro.Scenario):
    subject = "get_active_queue() does not return stale items when cache version changes mid-refresh"

    def given_queue_manager_and_race_condition(self):
        self.qm = QueueManager(db=None)  # type: ignore[arg-type]

        queued_at = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
        self._old_rows = [
            {
                "iid": 1,
                "title": "Old",
                "author_name": "A",
                "author_username": "a",
                "author_avatar": None,
                "status": "queued",
                "is_hotfix": 0,
                "labels": "[]",
                "target_branch": "main",
                "queued_at": queued_at,
                "started_at": None,
                "finished_at": None,
                "pipeline_id": None,
                "pipeline_status": None,
                "expected_sha": None,
                "retry_count": 0,
                "last_error": None,
                "stale_warning_sent": 0,
            }
        ]

        self.new_items = ["NEW_ITEMS_SENTINEL"]

        def _interleave_cache_update() -> None:
            if self.qm._cache.version == 0:
                self.qm._cache.invalidate()  # version -> 1
                self.qm._cache.set_active_queue(self.new_items, version=self.qm._cache.version)  # type: ignore[arg-type]

        self.qm.db = _FakeDB(rows=self._old_rows, on_execute=_interleave_cache_update)  # type: ignore[assignment]

    async def when_active_queue_is_requested(self):
        self.result = await self.qm.get_active_queue()

    def then_returned_queue_is_the_new_cached_value(self):
        assert self.result is self.new_items
