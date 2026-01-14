"""Test scenarios for GitLabClient rebase operations.

Tests rebase-related methods including:
- rebase_mr()
- check_rebase_status()
- get_mr_conflicts()
"""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import (
    mock_gitlab_get_conflicts,
    mock_gitlab_get_mr,
    mock_gitlab_rebase,
)

from gitlab_queue.clients.gitlab import GitLabConflictError


def create_mr_response_for_rebase(
    iid: int = 42,
    rebase_in_progress: bool = False,
    has_conflicts: bool = False,
) -> dict:
    """Create a GitLab MR API response for rebase status testing."""
    return {
        "iid": iid,
        "title": "Test MR",
        "state": "opened",
        "labels": ["merge_queue"],
        "sha": "abc123",
        "source_branch": "feature",
        "target_branch": "master",
        "merge_status": "cannot_be_merged" if has_conflicts else "can_be_merged",
        "has_conflicts": has_conflicts,
        "rebase_in_progress": rebase_in_progress,
        "author": {
            "id": 1,
            "name": "Test User",
            "username": "testuser",
        },
    }


class Scenario__rebase_mr_initiates_rebase(vedro.Scenario):
    subject = "rebase_mr initiates rebase successfully"

    async def given_mock_gitlab_for_rebase(self):
        self._mock_ctx = mock_gitlab_rebase(TEST_PROJECT_ID, 42, success=True)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_rebase_mr_is_called(self):
        self.result = await self.client.rebase_mr(42)

    def then_result_should_be_true(self):
        assert self.result is True

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__rebase_mr_raises_conflict_on_409(vedro.Scenario):
    subject = "rebase_mr raises GitLabConflictError on 409"

    async def given_mock_gitlab_returns_conflict(self):
        self._mock_ctx = mock_gitlab_rebase(TEST_PROJECT_ID, 42, success=False)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_rebase_mr_is_called(self):
        self.error = None
        try:
            await self.client.rebase_mr(42)
        except GitLabConflictError as e:
            self.error = e

    def then_error_should_be_raised(self):
        assert self.error is not None

    def and_error_should_be_conflict_error(self):
        assert isinstance(self.error, GitLabConflictError)

    def and_status_code_should_be_409(self):
        assert self.error.status_code == 409

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__check_rebase_status_in_progress(vedro.Scenario):
    subject = "check_rebase_status returns in_progress=True when rebasing"

    async def given_mock_gitlab_with_rebasing_mr(self):
        mr_data = create_mr_response_for_rebase(rebase_in_progress=True)
        self._mock_ctx = mock_gitlab_get_mr(TEST_PROJECT_ID, 42, mr_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_check_rebase_status_is_called(self):
        self.in_progress, self.has_conflicts = await self.client.check_rebase_status(42)

    def then_in_progress_should_be_true(self):
        assert self.in_progress is True

    def and_has_conflicts_should_be_false(self):
        assert self.has_conflicts is False

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__check_rebase_status_completed(vedro.Scenario):
    subject = "check_rebase_status returns in_progress=False when completed"

    async def given_mock_gitlab_with_completed_rebase(self):
        mr_data = create_mr_response_for_rebase(rebase_in_progress=False)
        self._mock_ctx = mock_gitlab_get_mr(TEST_PROJECT_ID, 42, mr_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_check_rebase_status_is_called(self):
        self.in_progress, self.has_conflicts = await self.client.check_rebase_status(42)

    def then_in_progress_should_be_false(self):
        assert self.in_progress is False

    def and_has_conflicts_should_be_false(self):
        assert self.has_conflicts is False

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__check_rebase_status_with_conflicts(vedro.Scenario):
    subject = "check_rebase_status returns has_conflicts=True when conflicts exist"

    async def given_mock_gitlab_with_conflicting_mr(self):
        mr_data = create_mr_response_for_rebase(
            rebase_in_progress=False,
            has_conflicts=True,
        )
        self._mock_ctx = mock_gitlab_get_mr(TEST_PROJECT_ID, 42, mr_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_check_rebase_status_is_called(self):
        self.in_progress, self.has_conflicts = await self.client.check_rebase_status(42)

    def then_in_progress_should_be_false(self):
        assert self.in_progress is False

    def and_has_conflicts_should_be_true(self):
        assert self.has_conflicts is True

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__get_mr_conflicts_returns_files(vedro.Scenario):
    subject = "get_mr_conflicts returns list of conflicted files"

    async def given_mock_gitlab_with_conflicts(self):
        self.conflicts_data = [
            {"old_path": "src/main.py", "new_path": "src/main.py"},
            {"old_path": "config.yml", "new_path": "config.yml"},
            {"old_path": "old/file.py", "new_path": "new/file.py"},
        ]
        self._mock_ctx = mock_gitlab_get_conflicts(TEST_PROJECT_ID, 42, self.conflicts_data)
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


class Scenario__get_mr_conflicts_returns_empty_on_error(vedro.Scenario):
    subject = "get_mr_conflicts returns empty list on API error"

    async def given_mock_gitlab_returns_404(self):
        self._mock_ctx = mock_gitlab_get_conflicts(
            TEST_PROJECT_ID, 42, {"message": "Not Found"}, status=404
        )
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_conflicts_is_called(self):
        # Should not raise, returns empty list as fallback
        self.result = await self.client.get_mr_conflicts(42)

    def then_result_should_be_empty(self):
        assert self.result == []

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__get_mr_conflicts_uses_old_path_fallback(vedro.Scenario):
    subject = "get_mr_conflicts uses old_path when new_path is missing"

    async def given_mock_gitlab_with_old_path_only(self):
        self.conflicts_data = [
            {"old_path": "legacy.py"},  # No new_path
        ]
        self._mock_ctx = mock_gitlab_get_conflicts(TEST_PROJECT_ID, 42, self.conflicts_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_conflicts_is_called(self):
        self.result = await self.client.get_mr_conflicts(42)

    def then_result_should_contain_old_path(self):
        assert self.result == ["legacy.py"]

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
