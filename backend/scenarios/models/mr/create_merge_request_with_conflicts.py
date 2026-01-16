"""Unit tests for MergeRequest and Author models."""

import vedro

from gitlab_queue.models.mr import Author, MergeRequest


class Scenario(vedro.Scenario):
    subject = "create merge request with conflicts"

    def given_author(self):
        self.author = Author(id=1, name="Test", username="test")

    def when_mr_with_conflicts_is_created(self):
        self.mr = MergeRequest(
            iid=456,
            title="Feature branch",
            state="opened",
            labels=[],
            sha="def789",
            source_branch="feature",
            target_branch="master",
            merge_status="cannot_be_merged",
            author=self.author,
            has_conflicts=True,
        )

    def then_it_should_indicate_conflicts(self):
        assert self.mr.has_conflicts is True
        assert self.mr.merge_status == "cannot_be_merged"
