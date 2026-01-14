"""Test scenarios for GitLabClient.list_mrs_with_label() method.

Tests listing merge requests with label filter including:
- Successful listing with multiple MRs
- Empty list when no MRs match
- Label filtering
"""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mock_gitlab_list_mrs


def create_mr_api_response(
    iid: int,
    title: str = "Test MR",
    state: str = "opened",
    labels: list[str] | None = None,
) -> dict:
    """Create a minimal GitLab MR API response for testing."""
    return {
        "iid": iid,
        "title": title,
        "state": state,
        "labels": labels or ["merge_queue"],
        "sha": f"sha{iid}",
        "source_branch": f"feature-{iid}",
        "target_branch": "master",
        "merge_status": "can_be_merged",
        "has_conflicts": False,
        "rebase_in_progress": False,
        "author": {
            "id": iid,
            "name": f"User {iid}",
            "username": f"user{iid}",
        },
    }


class Scenario__list_mrs_returns_empty_list(vedro.Scenario):
    subject = "list_mrs_with_label returns empty list when no MRs"

    async def given_mock_gitlab_with_no_mrs(self):
        self._mock_ctx = mock_gitlab_list_mrs(TEST_PROJECT_ID, [], label="merge_queue")
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_list_mrs_is_called(self):
        self.result = await self.client.list_mrs_with_label("merge_queue")

    def then_result_should_be_empty_list(self):
        assert self.result == []

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__list_mrs_returns_multiple_mrs(vedro.Scenario):
    subject = "list_mrs_with_label returns multiple MRs"

    async def given_mock_gitlab_with_multiple_mrs(self):
        self.mrs_data = [
            create_mr_api_response(iid=1, title="First MR"),
            create_mr_api_response(iid=2, title="Second MR"),
            create_mr_api_response(iid=3, title="Third MR"),
        ]
        self._mock_ctx = mock_gitlab_list_mrs(TEST_PROJECT_ID, self.mrs_data, label="merge_queue")
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_list_mrs_is_called(self):
        self.result = await self.client.list_mrs_with_label("merge_queue")

    def then_result_should_have_three_mrs(self):
        assert len(self.result) == 3

    def and_first_mr_should_have_correct_iid(self):
        assert self.result[0].iid == 1

    def and_second_mr_should_have_correct_iid(self):
        assert self.result[1].iid == 2

    def and_third_mr_should_have_correct_iid(self):
        assert self.result[2].iid == 3

    def and_titles_should_match(self):
        assert self.result[0].title == "First MR"
        assert self.result[1].title == "Second MR"
        assert self.result[2].title == "Third MR"

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__list_mrs_parses_all_fields(vedro.Scenario):
    subject = "list_mrs_with_label parses MR fields correctly"

    async def given_mock_gitlab_with_detailed_mr(self):
        self.mrs_data = [
            create_mr_api_response(
                iid=42,
                title="Detailed MR",
                state="opened",
                labels=["merge_queue", "feature"],
            ),
        ]
        self._mock_ctx = mock_gitlab_list_mrs(TEST_PROJECT_ID, self.mrs_data, label="merge_queue")
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_list_mrs_is_called(self):
        self.result = await self.client.list_mrs_with_label("merge_queue")

    def then_mr_fields_should_be_parsed(self):
        mr = self.result[0]
        assert mr.iid == 42
        assert mr.title == "Detailed MR"
        assert mr.state == "opened"
        assert mr.labels == ["merge_queue", "feature"]
        assert mr.source_branch == "feature-42"
        assert mr.target_branch == "master"

    def and_author_should_be_parsed(self):
        mr = self.result[0]
        assert mr.author.id == 42
        assert mr.author.username == "user42"

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__list_mrs_filters_by_state(vedro.Scenario):
    subject = "list_mrs_with_label accepts state parameter"

    async def given_mock_gitlab_with_closed_mr(self):
        self.mrs_data = [
            create_mr_api_response(iid=1, state="closed"),
        ]
        self._mock_ctx = mock_gitlab_list_mrs(TEST_PROJECT_ID, self.mrs_data, label="merge_queue")
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_list_mrs_is_called_with_state(self):
        # Note: The mock doesn't verify state param, but we verify the method accepts it
        self.result = await self.client.list_mrs_with_label("merge_queue", state="closed")

    def then_result_should_contain_closed_mr(self):
        assert len(self.result) == 1
        assert self.result[0].state == "closed"

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
