"""Test that path traversal attempts are rejected during initialization."""

from __future__ import annotations

import tempfile

import vedro
from vedro import catched

from gitlab_queue.db.database import Database, DatabaseConfigurationError


class Scenario(vedro.Scenario):
    subject = "path validation rejects traversal attempts"

    def given_database_with_traversal_path(self):
        """
        Prepare a Database instance using a traversal-style URL and a temporary allowed base path.
        
        Creates a TemporaryDirectory stored on self._tmp_dir and constructs self.db with
        database_url "sqlite+aiosqlite:///../../etc/passwd" and allowed_base_path set to
        the temporary directory's path for use in subsequent initialization tests.
        """
        self._tmp_dir = tempfile.TemporaryDirectory()
        # Attempt path traversal outside allowed base path
        traversal_url = "sqlite+aiosqlite:///../../etc/passwd"
        self.db = Database(
            database_url=traversal_url,
            allowed_base_path=self._tmp_dir.name,
        )

    async def when_database_initialization_is_attempted(self):
        """
        Attempts to initialize the test Database and capture any DatabaseConfigurationError.
        
        If Database.initialize() raises DatabaseConfigurationError, the exception info is stored in self.exc_info via the catched context manager for later assertions.
        """
        with catched(DatabaseConfigurationError) as self.exc_info:
            await self.db.initialize()

    def then_database_configuration_error_is_raised(self):
        """
        Asserts that the previously captured exception is a DatabaseConfigurationError.
        """
        assert self.exc_info.type is DatabaseConfigurationError

    def and_error_message_mentions_path_traversal(self):
        """
        Asserts that the captured DatabaseConfigurationError message indicates a path traversal outside the allowed directory.
        
        Raises:
            AssertionError: If the exception message does not contain "outside allowed directory".
        """
        assert "outside allowed directory" in str(self.exc_info.value)

    def do_cleanup(self):
        """
        Remove the temporary directory created for the scenario.
        """
        self._tmp_dir.cleanup()
