"""Test scenario: get_mr_conflicts returns list of conflicted files."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_conflicts


class Scenario(vedro.Scenario):
    subject = "get_mr_conflicts returns list of conflicted files"

    async def given_mock_gitlab_with_conflicts(self):
        self.conflicts_data = [
            {"old_path": "src/main.py", "new_path": "src/main.py"},
            {"old_path": "config.yml", "new_path": "config.yml"},
            {"old_path": "old/file.py", "new_path": "new/file.py"},
        ]
        self._mock_ctx = mocked_gitlab_get_conflicts(TEST_PROJECT_ID, 42, self.conflicts_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_conflicts_is_called(self):
        self.result = await self.client.get_mr_conflicts(42)

    def then_result_should_have_three_files(self):
        assert len(self.result) == 3

    def and_files_should_be_new_paths(self):
        # new_path is preferred over old_path
        assert "src/main.py" in self.result
        assert "config.yml" in self.result
        assert "new/file.py" in self.result

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
