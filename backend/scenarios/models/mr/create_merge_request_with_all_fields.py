"""Unit tests for MergeRequest and Author models."""

import vedro

from gitlab_queue.models.mr import Author, MergeRequest


class Scenario(vedro.Scenario):
    subject = "create merge request with all fields"

    def given_mr_data(self):
        self.author = Author(
            id=42,
            name="John Doe",
            username="johndoe",
            avatar_url="https://gitlab.com/avatar.png",
        )

    def when_mr_is_created(self):
        self.mr = MergeRequest(
            iid=123,
            title="Fix critical bug",
            state="opened",
            labels=["bug", "urgent"],
            sha="abc123def456",
            source_branch="fix-bug",
            target_branch="master",
            merge_status="can_be_merged",
            author=self.author,
            has_conflicts=False,
            rebase_in_progress=False,
            web_url="https://gitlab.com/project/-/merge_requests/123",
        )

    def then_it_should_have_correct_fields(self):
        assert self.mr.iid == 123
        assert self.mr.title == "Fix critical bug"
        assert self.mr.state == "opened"
        assert self.mr.labels == ["bug", "urgent"]
        assert self.mr.sha == "abc123def456"
        assert self.mr.source_branch == "fix-bug"
        assert self.mr.target_branch == "master"
        assert self.mr.merge_status == "can_be_merged"
        assert self.mr.author == self.author
        assert self.mr.has_conflicts is False
        assert self.mr.rebase_in_progress is False
        assert self.mr.web_url == "https://gitlab.com/project/-/merge_requests/123"
