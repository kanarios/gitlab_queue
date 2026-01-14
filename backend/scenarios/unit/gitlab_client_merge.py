"""Test scenarios for GitLabClient.merge_mr() method.

Tests merge operation including:
- Successful merge with fast-forward strategy
- Merge status check before merge
- Error handling when MR is not mergeable
"""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mock_gitlab_get_mr, mock_gitlab_merge

from gitlab_queue.clients.gitlab import GitLabConflictError


def create_mr_response(
    iid: int = 42,
    state: str = "opened",
    merge_status: str = "can_be_merged",
    has_conflicts: bool = False,
) -> dict:
    """Create a GitLab MR API response for merge testing."""
    return {
        "iid": iid,
        "title": "Test MR",
        "state": state,
        "labels": ["merge_queue"],
        "sha": "abc123",
        "source_branch": "feature",
        "target_branch": "master",
        "merge_status": merge_status,
        "has_conflicts": has_conflicts,
        "rebase_in_progress": False,
        "author": {
            "id": 1,
            "name": "Test User",
            "username": "testuser",
        },
    }


class Scenario__merge_mr_succeeds(vedro.Scenario):
    subject = "merge_mr merges MR successfully"

    async def given_mock_gitlab_with_mergeable_mr(self):
        # First call: get_mr to check merge_status
        mr_data = create_mr_response(iid=42, merge_status="can_be_merged")
        self._get_mock = mock_gitlab_get_mr(TEST_PROJECT_ID, 42, mr_data)
        await self._get_mock.__aenter__()

        # Second call: merge endpoint
        merged_data = create_mr_response(iid=42, state="merged", merge_status="merged")
        self._merge_mock = mock_gitlab_merge(
            TEST_PROJECT_ID, 42, success=True, merged_data=merged_data
        )
        await self._merge_mock.__aenter__()

        self.client = create_test_client()

    async def when_merge_mr_is_called(self):
        self.result = await self.client.merge_mr(42)

    def then_result_should_be_merged_mr(self):
        assert self.result is not None
        assert self.result.iid == 42

    def and_state_should_be_merged(self):
        assert self.result.state == "merged"

    async def do_cleanup(self):
        await self.client.close()
        await self._merge_mock.__aexit__(None, None, None)
        await self._get_mock.__aexit__(None, None, None)


class Scenario__merge_mr_raises_conflict_when_not_mergeable(vedro.Scenario):
    subject = "merge_mr raises GitLabConflictError when MR is not mergeable"

    async def given_mock_gitlab_with_unmergeable_mr(self):
        # MR has conflicts - cannot be merged
        mr_data = create_mr_response(
            iid=42,
            merge_status="cannot_be_merged",
            has_conflicts=True,
        )
        self._get_mock = mock_gitlab_get_mr(TEST_PROJECT_ID, 42, mr_data)
        await self._get_mock.__aenter__()
        self.client = create_test_client()

    async def when_merge_mr_is_called(self):
        self.error = None
        try:
            await self.client.merge_mr(42)
        except GitLabConflictError as e:
            self.error = e

    def then_error_should_be_raised(self):
        assert self.error is not None

    def and_error_should_be_conflict_error(self):
        assert isinstance(self.error, GitLabConflictError)

    def and_error_message_should_mention_status(self):
        assert "cannot_be_merged" in str(self.error)

    async def do_cleanup(self):
        await self.client.close()
        await self._get_mock.__aexit__(None, None, None)


class Scenario__merge_mr_raises_conflict_when_unchecked(vedro.Scenario):
    subject = "merge_mr raises GitLabConflictError when merge_status is unchecked"

    async def given_mock_gitlab_with_unchecked_mr(self):
        # MR merge status not yet determined
        mr_data = create_mr_response(
            iid=42,
            merge_status="unchecked",
        )
        self._get_mock = mock_gitlab_get_mr(TEST_PROJECT_ID, 42, mr_data)
        await self._get_mock.__aenter__()
        self.client = create_test_client()

    async def when_merge_mr_is_called(self):
        self.error = None
        try:
            await self.client.merge_mr(42)
        except GitLabConflictError as e:
            self.error = e

    def then_error_should_be_raised(self):
        assert self.error is not None

    def and_error_message_should_mention_unchecked(self):
        assert "unchecked" in str(self.error)

    async def do_cleanup(self):
        await self.client.close()
        await self._get_mock.__aexit__(None, None, None)


class Scenario__merge_mr_returns_merged_state(vedro.Scenario):
    subject = "merge_mr returns MR with merged state"

    async def given_mock_gitlab_for_successful_merge(self):
        # Check merge status
        mr_data = create_mr_response(iid=99, merge_status="can_be_merged")
        self._get_mock = mock_gitlab_get_mr(TEST_PROJECT_ID, 99, mr_data)
        await self._get_mock.__aenter__()

        # Merge returns merged MR
        merged_data = create_mr_response(
            iid=99,
            state="merged",
            merge_status="merged",
        )
        self._merge_mock = mock_gitlab_merge(
            TEST_PROJECT_ID, 99, success=True, merged_data=merged_data
        )
        await self._merge_mock.__aenter__()
        self.client = create_test_client()

    async def when_merge_mr_is_called(self):
        self.result = await self.client.merge_mr(99)

    def then_iid_should_match(self):
        assert self.result.iid == 99

    def and_state_should_be_merged(self):
        assert self.result.state == "merged"

    def and_merge_status_should_be_merged(self):
        assert self.result.merge_status == "merged"

    async def do_cleanup(self):
        await self.client.close()
        await self._merge_mock.__aexit__(None, None, None)
        await self._get_mock.__aexit__(None, None, None)
