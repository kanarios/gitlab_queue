"""Helpers for MRNotifier unit test scenarios."""

from __future__ import annotations

from gitlab_queue.core.notifier import MRNotifier
from scenarios.fakes import FakeGitLabClient, FakeSettings


def create_test_notifier(
    *,
    gitlab_client: FakeGitLabClient | None = None,
    settings: FakeSettings | None = None,
) -> MRNotifier:
    """Create an MRNotifier with typed fakes for testing.

    Parameters:
        gitlab_client: If None, a default FakeGitLabClient is created.
        settings: If None, a default FakeSettings is created.

    Returns:
        MRNotifier configured for testing.
    """
    if gitlab_client is None:
        gitlab_client = FakeGitLabClient()
    if settings is None:
        settings = FakeSettings()
    return MRNotifier(gitlab_client=gitlab_client, settings=settings)


__all__ = ["create_test_notifier"]
