"""Helpers for MRNotifier unit test scenarios."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from gitlab_queue.core.notifier import MRNotifier


def create_test_notifier(*, gitlab_client=None, settings=None):
    """
    Create an MRNotifier configured with mocked GitLab client and settings for use in tests.
    
    Parameters:
        gitlab_client (Optional[unittest.mock.AsyncMock]): If None, an AsyncMock is created and configured so
            its add_or_update_pinned_comment returns a mock note with id = 1.
        settings (Optional[unittest.mock.MagicMock]): If None, a MagicMock is created with
            queue_label = "merge_queue" and gitlab_url = "https://gitlab.example.com/group/project".
    
    Returns:
        MRNotifier: An MRNotifier instance initialized with the provided or automatically created mocks.
    """
    if gitlab_client is None:
        gitlab_client = AsyncMock()
        note = MagicMock()
        note.id = 1
        gitlab_client.add_or_update_pinned_comment.return_value = note
    if settings is None:
        settings = MagicMock()
        settings.queue_label = "merge_queue"
        settings.gitlab_url = "https://gitlab.example.com/group/project"
    return MRNotifier(gitlab_client=gitlab_client, settings=settings)


__all__ = ["create_test_notifier"]
