"""Helpers for MRNotifier unit test scenarios."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from gitlab_queue.core.notifier import MRNotifier


def create_test_notifier(*, gitlab_client=None, settings=None):
    """Create MRNotifier with mock dependencies.

    Args:
        gitlab_client: Optional mock GitLab client. Created automatically if None.
        settings: Optional mock settings. Created automatically if None.

    Returns:
        MRNotifier instance ready for testing.
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
