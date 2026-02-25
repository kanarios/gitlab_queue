"""Test scenario: sync operation adds MRs missing from local queue."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import vedro

from gitlab_queue.core.scheduler import QueueScheduler


def create_mock_settings(**overrides: object) -> MagicMock:
    """Create mock Settings for scheduler tests."""
    settings = MagicMock()
    defaults = {
        "queue_label": "merge_queue",
        "hotfix_label": "hotfix",
        "target_branch": "main",
        "poll_interval_seconds": 60,
        "rate_limit_critical_threshold": 0.95,
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(settings, key, value)
    return settings


def create_mock_gitlab_mr(iid: int, labels: list[str] | None = None) -> MagicMock:
    """Create a mock MergeRequest from GitLab API."""
    from gitlab_queue.models.mr import Author, MergeRequest

    mr = MergeRequest(
        iid=iid,
        title=f"MR !{iid}",
        state="opened",
        labels=labels or ["merge_queue"],
        sha=f"sha{iid}",
        source_branch=f"feature-{iid}",
        target_branch="main",
        merge_status="can_be_merged",
        author=Author(id=iid, name=f"User {iid}", username=f"user{iid}"),
    )
    return mr


def create_mock_gitlab_client() -> MagicMock:
    """Create mock GitLabClient."""
    client = MagicMock()
    rate_limit = MagicMock()
    rate_limit.is_critical.return_value = False
    type(client).rate_limit_state = PropertyMock(return_value=rate_limit)
    return client


def create_mock_queue_manager() -> MagicMock:
    """Create mock QueueManager."""
    qm = MagicMock()
    qm.get_active_queue = AsyncMock(return_value=[])
    qm.add_to_queue = AsyncMock()
    qm.get_queue_stats = AsyncMock(return_value={})
    return qm


class Scenario(vedro.Scenario):
    subject = "sync adds mrs that are in gitlab but missing from queue"

    def given_scheduler_with_missing_mrs(self):
        self.gitlab_client = create_mock_gitlab_client()

        # GitLab returns two MRs with queue label
        self.gitlab_mrs = [
            create_mock_gitlab_mr(iid=10),
            create_mock_gitlab_mr(iid=20),
        ]
        self.gitlab_client.list_mrs_with_label = AsyncMock(
            side_effect=[
                self.gitlab_mrs,  # queue label MRs
                [],  # hotfix label MRs
            ]
        )

        self.queue_manager = create_mock_queue_manager()
        # Queue is currently empty - both MRs are "missing"
        self.queue_manager.get_active_queue = AsyncMock(return_value=[])

        self.settings = create_mock_settings()
        self.scheduler = QueueScheduler(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            settings=self.settings,
        )

    async def when_sync_is_performed(self):
        self.stats = await self.scheduler.sync_queue()

    def then_added_count_should_be_two(self):
        assert self.stats.added == 2

    def and_queue_manager_should_have_added_both_mrs(self):
        assert self.queue_manager.add_to_queue.call_count == 2

    def and_mrs_in_gitlab_should_be_two(self):
        assert self.stats.mrs_in_gitlab == 2
