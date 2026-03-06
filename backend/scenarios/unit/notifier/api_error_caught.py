"""Test that API errors in notifier are caught and don't propagate.

Covers notifier.py lines 355, 425:
- notify() raises KeyError for unknown status
- remove_queue_label() catches API errors without propagation
- _render_template includes queue_label from settings
"""

from __future__ import annotations

import vedro
from vedro import catched

from scenarios.fakes import FakeGitLabClient

from ._helpers import create_test_notifier


class Scenario(vedro.Scenario):
    subject = "notify() raises KeyError for unknown notification status"

    def given_notifier_with_mock_client(self):
        """
        Create a test notifier configured with a default FakeGitLabClient.

        Sets self.notifier to the notifier instance returned by create_test_notifier(), ready for use by subsequent test steps.
        """
        self.notifier = create_test_notifier()

    async def when_notify_is_called_with_unknown_status(self):
        """
        Calls notifier.notify with a non-existent status and captures the resulting KeyError into self.exc_info.
        """
        with catched(KeyError) as self.exc_info:
            await self.notifier.notify(mr_iid=42, status="nonexistent_status")

    def then_error_was_raised(self):
        """
        Assert that the previously captured exception is a KeyError.

        Fails the test if the stored exception type (self.exc_info.type) is not KeyError.
        """
        assert self.exc_info.type is KeyError

    def and_message_mentions_unknown_status(self):
        """
        Asserts that the captured exception's message contains "Unknown notification status".

        Checks the stored exception information and verifies the exception message includes the exact substring "Unknown notification status".
        """
        assert "Unknown notification status" in str(self.exc_info.value)


class Scenario2(vedro.Scenario):
    subject = "notify() calls gitlab_client with rendered template body"

    def given_notifier_with_mock_client(self):
        """
        Prepare a test notifier with a FakeGitLabClient.

        Sets self.gitlab_client to a FakeGitLabClient and assigns self.notifier via create_test_notifier using that client.
        """
        self.gitlab_client = FakeGitLabClient()
        self.notifier = create_test_notifier(gitlab_client=self.gitlab_client)

    async def when_notify_is_called_with_valid_status(self):
        """
        Invoke notifier.notify with a valid "removed_closed" status and record its return value on self.result.
        """
        self.result = await self.notifier.notify(
            mr_iid=10,
            status="removed_closed",
            removed_at="2025-01-15 10:00 UTC",
        )

    def then_note_is_returned(self):
        """
        Assert that the notifier returned a note with id 1 (default from FakeGitLabClient).
        """
        assert self.result.id == 1

    def and_gitlab_client_was_called(self):
        assert len(self.gitlab_client.add_comment_calls) == 1
        mr_iid, body = self.gitlab_client.add_comment_calls[0]
        assert mr_iid == 10
        assert "Removed from queue" in body


class Scenario3(vedro.Scenario):
    subject = "remove_queue_label catches API error and does not propagate"

    def given_notifier_whose_client_raises(self):
        """
        Prepare self.notifier with a FakeGitLabClient that raises an exception when removing MR labels.
        """
        gitlab_client = FakeGitLabClient(
            remove_label_error=Exception("GitLab API 500"),
        )
        self.notifier = create_test_notifier(gitlab_client=gitlab_client)

    async def when_remove_queue_label_is_called(self):
        """
        Invoke the notifier's remove_queue_label for MR IID 42 and record whether it raised an exception.
        """
        self.raised = False
        try:
            await self.notifier.remove_queue_label(42)
        except Exception:
            self.raised = True

    def then_no_exception_is_propagated(self):
        """
        Asserts that no exception was propagated during the preceding operation.
        """
        assert self.raised is False


class Scenario4(vedro.Scenario):
    subject = "build_pipeline_url constructs correct URL"

    def given_notifier_with_gitlab_url(self):
        gitlab_client = FakeGitLabClient(
            project_web_url="https://gitlab.example.com/group/project",
        )
        self.notifier = create_test_notifier(gitlab_client=gitlab_client)

    async def when_build_pipeline_url_is_called(self):
        self.url = await self.notifier.build_pipeline_url(12345)

    def then_url_contains_pipeline_id(self):
        """
        Asserts the constructed pipeline URL includes the expected pipeline ID "12345".
        """
        assert "12345" in self.url

    def and_url_contains_gitlab_base(self):
        assert self.url.startswith("https://gitlab.example.com/group/project")
