"""Unit tests for webhook event models."""

import vedro

from gitlab_queue.models.events import MergeRequestAttributes


class Scenario(vedro.Scenario):
    subject = "create merge request attributes"

    def given_mr_attributes_data(self):
        self.iid = 123
        self.title = "Fix bug"
        self.state = "opened"
        self.action = "update"

    def when_mr_attributes_are_created(self):
        self.attrs = MergeRequestAttributes(
            iid=self.iid,
            title=self.title,
            state=self.state,
            action=self.action,
            source_branch="fix-branch",
            target_branch="master",
            merge_status="can_be_merged",
        )

    def then_it_should_have_correct_fields(self):
        assert self.attrs.iid == self.iid
        assert self.attrs.title == self.title
        assert self.attrs.state == self.state
        assert self.attrs.action == self.action
        assert self.attrs.source_branch == "fix-branch"
        assert self.attrs.target_branch == "master"

    def and_it_should_have_default_optional_fields(self):
        assert self.attrs.sha is None
        assert self.attrs.has_conflicts is False
        assert self.attrs.rebase_in_progress is False
        assert self.attrs.web_url is None
