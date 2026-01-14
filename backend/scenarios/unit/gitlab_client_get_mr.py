"""Test scenarios for GitLabClient.get_mr() method.

Tests fetching merge requests by IID including:
- Successful fetch with all fields populated
- 404 error handling
- Model parsing verification
"""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mock_gitlab_get_mr

from gitlab_queue.clients.gitlab import GitLabNotFoundError


def create_mr_api_response(
    iid: int = 42,
    title: str = "Test MR",
    state: str = "opened",
    labels: list[str] | None = None,
    sha: str = "abc123def456",
    source_branch: str = "feature-branch",
    target_branch: str = "master",
    merge_status: str = "can_be_merged",
    has_conflicts: bool = False,
    rebase_in_progress: bool = False,
) -> dict:
    """Create a minimal GitLab MR API response for testing."""
    return {
        "iid": iid,
        "title": title,
        "state": state,
        "labels": labels or ["feature"],
        "sha": sha,
        "source_branch": source_branch,
        "target_branch": target_branch,
        "merge_status": merge_status,
        "has_conflicts": has_conflicts,
        "rebase_in_progress": rebase_in_progress,
        "author": {
            "id": 1,
            "name": "Test User",
            "username": "testuser",
            "avatar_url": "https://gitlab.com/avatar.png",
        },
        "web_url": f"https://gitlab.com/project/-/merge_requests/{iid}",
    }


class Scenario__get_mr_returns_merge_request(vedro.Scenario):
    subject = "get_mr returns MergeRequest model"

    async def given_mock_gitlab_with_mr(self):
        self.mr_data = create_mr_api_response(iid=42, title="Test MR")
        self._mock_ctx = mock_gitlab_get_mr(TEST_PROJECT_ID, 42, self.mr_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_is_called(self):
        self.result = await self.client.get_mr(42)

    def then_result_should_be_merge_request(self):
        assert self.result is not None

    def and_iid_should_match(self):
        assert self.result.iid == 42

    def and_title_should_match(self):
        assert self.result.title == "Test MR"

    def and_state_should_match(self):
        assert self.result.state == "opened"

    def and_author_should_be_parsed(self):
        assert self.result.author.id == 1
        assert self.result.author.name == "Test User"
        assert self.result.author.username == "testuser"

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__get_mr_returns_all_fields(vedro.Scenario):
    subject = "get_mr parses all MR fields correctly"

    async def given_mock_gitlab_with_full_mr(self):
        self.mr_data = create_mr_api_response(
            iid=99,
            title="Full MR Test",
            state="merged",
            labels=["bug", "critical"],
            sha="full123sha",
            source_branch="hotfix",
            target_branch="main",
            merge_status="merged",
            has_conflicts=False,
            rebase_in_progress=False,
        )
        self._mock_ctx = mock_gitlab_get_mr(TEST_PROJECT_ID, 99, self.mr_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_is_called(self):
        self.result = await self.client.get_mr(99)

    def then_sha_should_match(self):
        assert self.result.sha == "full123sha"

    def and_source_branch_should_match(self):
        assert self.result.source_branch == "hotfix"

    def and_target_branch_should_match(self):
        assert self.result.target_branch == "main"

    def and_merge_status_should_match(self):
        assert self.result.merge_status == "merged"

    def and_labels_should_match(self):
        assert self.result.labels == ["bug", "critical"]

    def and_has_conflicts_should_be_false(self):
        assert self.result.has_conflicts is False

    def and_rebase_in_progress_should_be_false(self):
        assert self.result.rebase_in_progress is False

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__get_mr_with_conflicts(vedro.Scenario):
    subject = "get_mr parses has_conflicts field"

    async def given_mock_gitlab_with_conflicting_mr(self):
        self.mr_data = create_mr_api_response(
            iid=50,
            has_conflicts=True,
            merge_status="cannot_be_merged",
        )
        self._mock_ctx = mock_gitlab_get_mr(TEST_PROJECT_ID, 50, self.mr_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_is_called(self):
        self.result = await self.client.get_mr(50)

    def then_has_conflicts_should_be_true(self):
        assert self.result.has_conflicts is True

    def and_merge_status_should_be_cannot_be_merged(self):
        assert self.result.merge_status == "cannot_be_merged"

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__get_mr_raises_not_found_on_404(vedro.Scenario):
    subject = "get_mr raises GitLabNotFoundError on 404"

    async def given_mock_gitlab_returns_404(self):
        self.mr_data = {"message": "404 Not Found"}
        self._mock_ctx = mock_gitlab_get_mr(TEST_PROJECT_ID, 999, self.mr_data, status=404)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_is_called_for_nonexistent_mr(self):
        self.error = None
        try:
            await self.client.get_mr(999)
        except GitLabNotFoundError as e:
            self.error = e

    def then_error_should_be_raised(self):
        assert self.error is not None

    def and_error_should_be_not_found(self):
        assert isinstance(self.error, GitLabNotFoundError)

    def and_status_code_should_be_404(self):
        assert self.error.status_code == 404

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
