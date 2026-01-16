"""Unit tests for MergeRequest and Author models."""

import vedro

from gitlab_queue.models.mr import Author, MergeRequest


class Scenario(vedro.Scenario):
    subject = "create merge request with rebase in progress"

    def given_author(self):
        self.author = Author(id=1, name="Test", username="test")

    def when_mr_with_rebase_is_created(self):
        self.mr = MergeRequest(
            iid=789,
            title="Rebasing MR",
            state="opened",
            labels=[],
            sha="ghi012",
            source_branch="rebasing-branch",
            target_branch="master",
            merge_status="checking",
            author=self.author,
            rebase_in_progress=True,
        )

    def then_it_should_indicate_rebase_in_progress(self):
        assert self.mr.rebase_in_progress is True
