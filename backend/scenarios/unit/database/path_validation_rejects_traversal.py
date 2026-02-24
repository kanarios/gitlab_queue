"""Test that path traversal attempts are rejected during initialization."""

from __future__ import annotations

import tempfile

import vedro
from vedro import catched

from gitlab_queue.db.database import Database, DatabaseConfigurationError


class Scenario(vedro.Scenario):
    subject = "path validation rejects traversal attempts"

    def given_database_with_traversal_path(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        # Attempt path traversal outside allowed base path
        traversal_url = "sqlite+aiosqlite:///../../etc/passwd"
        self.db = Database(
            database_url=traversal_url,
            allowed_base_path=self._tmp_dir.name,
        )

    async def when_database_initialization_is_attempted(self):
        with catched(DatabaseConfigurationError) as self.exc_info:
            await self.db.initialize()

    def then_database_configuration_error_is_raised(self):
        assert self.exc_info.type is DatabaseConfigurationError

    def and_error_message_mentions_path_traversal(self):
        assert "outside allowed directory" in str(self.exc_info.value)

    def do_cleanup(self):
        if hasattr(self, "_tmp_dir"):
            self._tmp_dir.cleanup()
