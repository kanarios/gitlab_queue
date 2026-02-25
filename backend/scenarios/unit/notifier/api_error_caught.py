"""Test that API errors in notifier are caught and don't propagate.

Covers notifier.py lines 355, 425:
- notify() raises KeyError for unknown status
- remove_queue_label() catches API errors without propagation
- _render_template includes queue_label from settings
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from vedro import catched

from ._helpers import create_test_notifier


class Scenario(vedro.Scenario):
    subject = "notify() raises KeyError for unknown notification status"

    def given_notifier_with_mock_client(self):
        """
        Create a test notifier configured with a default mock GitLab client.
        
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
        Prepare a test notifier with a mocked GitLab client whose add_or_update_pinned_comment returns a note with id 42.
        
        Sets self.gitlab_client to an AsyncMock configured so add_or_update_pinned_comment returns a MagicMock note (id=42) and assigns self.notifier via create_test_notifier using that client.
        """
        self.gitlab_client = AsyncMock()
        note = MagicMock()
        note.id = 42
        self.gitlab_client.add_or_update_pinned_comment = AsyncMock(
            return_value=note,
        )
        self.notifier = create_test_notifier(gitlab_client=self.gitlab_client)

    async def when_notify_is_called_with_valid_status(self):
        """
        Invoke notifier.notify with a valid "removed_closed" status and record its return value on self.result.
        
        Calls notify(mr_iid=10, status="removed_closed", removed_at="2025-01-15 10:00 UTC") and stores the returned note object in self.result for later assertions.
        """
        self.result = await self.notifier.notify(
            mr_iid=10,
            status="removed_closed",
            removed_at="2025-01-15 10:00 UTC",
        )

    def then_note_is_returned(self):
        """
        Assert that the notifier returned a note with id 42.
        
        Raises:
            AssertionError: If the returned object's `id` is not 42.
        """
        assert self.result.id == 42

    def and_gitlab_client_was_called(self):
        self.gitlab_client.add_or_update_pinned_comment.assert_awaited_once()
        call_args = self.gitlab_client.add_or_update_pinned_comment.call_args
        assert call_args[0][0] == 10  # mr_iid
        assert "Removed from queue" in call_args[0][1]


class Scenario3(vedro.Scenario):
    subject = "remove_queue_label catches API error and does not propagate"

    def given_notifier_whose_client_raises(self):
        """
        Prepare self.notifier with a mock GitLab client that raises an exception when removing MR labels.
        
        Configures an AsyncMock gitlab_client where calling remove_mr_label raises Exception("GitLab API 500") and add_or_update_pinned_comment returns a note object with id == 1. The created notifier is assigned to self.notifier.
        """
        gitlab_client = AsyncMock()
        gitlab_client.remove_mr_label = AsyncMock(
            side_effect=Exception("GitLab API 500"),
        )
        note = MagicMock()
        note.id = 1
        gitlab_client.add_or_update_pinned_comment = AsyncMock(return_value=note)
        self.notifier = create_test_notifier(gitlab_client=gitlab_client)

    async def when_remove_queue_label_is_called(self):
        """
        Invoke the notifier's remove_queue_label for MR IID 42 and record whether it raised an exception.
        
        Sets self.raised to `True` if an exception was raised during the call, `False` otherwise.
        """
        self.raised = False
        try:
            await self.notifier.remove_queue_label(42)
        except Exception:
            self.raised = True

    def then_no_exception_is_propagated(self):
        """
        Asserts that no exception was propagated during the preceding operation.
        
        Fails the test if an exception bubbled up (i.e., if self.raised is True).
        """
        assert self.raised is False


class Scenario4(vedro.Scenario):
    subject = "build_pipeline_url constructs correct URL"

    def given_notifier_with_gitlab_url(self):
        """
        Create a test notifier configured with a specific GitLab base URL and queue label.
        
        Sets self.notifier to a test notifier whose settings have queue_label="merge_queue"
        and gitlab_url="https://gitlab.example.com/group/project".
        """
        settings = MagicMock()
        settings.queue_label = "merge_queue"
        settings.gitlab_url = "https://gitlab.example.com/group/project"
        self.notifier = create_test_notifier(settings=settings)

    def when_build_pipeline_url_is_called(self):
        self.url = self.notifier.build_pipeline_url(12345)

    def then_url_contains_pipeline_id(self):
        """
        Asserts the constructed pipeline URL includes the expected pipeline ID "12345".
        """
        assert "12345" in self.url

    def and_url_contains_gitlab_base(self):
        assert self.url.startswith("https://gitlab.example.com/group/project")
