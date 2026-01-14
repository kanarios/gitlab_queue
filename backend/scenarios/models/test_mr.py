"""Unit tests for MergeRequest and Author models."""

import vedro

from gitlab_queue.models.mr import Author, MergeRequest, Note


class Scenario(vedro.Scenario):
    subject = "create author with required fields"

    def given_author_data(self):
        self.author_id = 42
        self.name = "John Doe"
        self.username = "johndoe"

    def when_author_is_created(self):
        self.author = Author(
            id=self.author_id,
            name=self.name,
            username=self.username,
        )

    def then_it_should_have_correct_fields(self):
        assert self.author.id == self.author_id
        assert self.author.name == self.name
        assert self.author.username == self.username
        assert self.author.avatar_url is None


class Scenario__author_is_frozen(vedro.Scenario):
    subject = "author is immutable (frozen)"

    def given_author(self):
        self.author = Author(id=1, name="Test", username="test")

    def when_trying_to_modify_author(self):
        try:
            self.author.name = "New Name"
            self.error = None
        except Exception as e:
            self.error = e

    def then_it_should_raise_frozen_error(self):
        assert self.error is not None
        assert (
            "frozen" in str(type(self.error).__name__).lower()
            or "cannot" in str(self.error).lower()
        )


class Scenario__create_merge_request(vedro.Scenario):
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


class Scenario__mr_with_conflicts(vedro.Scenario):
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


class Scenario__mr_with_rebase_in_progress(vedro.Scenario):
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


class Scenario__create_note(vedro.Scenario):
    subject = "create MR note"

    def given_note_data(self):
        self.author = Author(id=42, name="Bot", username="merge-queue-bot")

    def when_note_is_created(self):
        self.note = Note(
            id=999,
            body="Pipeline started: https://gitlab.com/pipeline/123",
            author=self.author,
            system=False,
        )

    def then_it_should_have_correct_fields(self):
        assert self.note.id == 999
        assert "Pipeline started" in self.note.body
        assert self.note.author == self.author
        assert self.note.system is False


class Scenario__create_system_note(vedro.Scenario):
    subject = "create system note"

    def given_system_author(self):
        self.author = Author(id=0, name="GitLab", username="gitlab")

    def when_system_note_is_created(self):
        self.note = Note(
            id=1000,
            body="changed the description",
            author=self.author,
            system=True,
        )

    def then_it_should_be_marked_as_system(self):
        assert self.note.system is True
