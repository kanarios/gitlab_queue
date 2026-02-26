from __future__ import annotations

from unittest.mock import MagicMock

import vedro

from gitlab_queue.core.queue import QueueCache


class Scenario(vedro.Scenario):
    subject = "queue cache stale data protection via version counter"

    def given_cache(self):
        self.cache = QueueCache()

    def when_cache_is_invalidated_and_stale_set_attempted(self):
        initial_items = [MagicMock()]
        self.cache.set_active_queue(initial_items, version=self.cache.version)
        assert self.cache.get_active_queue() is initial_items

        version_before = self.cache.version
        self.cache.invalidate()
        assert self.cache.version == version_before + 1
        assert self.cache.get_active_queue() is None

        stale_items = [MagicMock()]
        self.cache.set_active_queue(stale_items, version=version_before)

    def then_cache_should_remain_invalid(self):
        assert self.cache.get_active_queue() is None
