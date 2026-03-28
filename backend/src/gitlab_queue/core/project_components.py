"""Per-project component container for multi-project deployments.

Groups all project-specific dependencies (GitLabClient, processor, scheduler, etc.)
into a single unit that can be looked up by project_id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import ProjectConfig
    from gitlab_queue.core.notifier import MRNotifier
    from gitlab_queue.core.processor import MergeProcessor
    from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier
    from gitlab_queue.core.scheduler import QueueScheduler


@dataclass
class ProjectComponents:
    """Container for per-project runtime components.

    Each registered project gets its own GitLabClient (with per-project token
    and circuit breaker), notifier, position notifier, processor, and scheduler.
    Shared components (database, queue_manager) are NOT included here —
    they are application-wide singletons.

    Attributes:
        config: Per-project configuration (project_id, token, labels, etc.)
        gitlab_client: GitLab API client scoped to this project.
        notifier: MR comment notifier using this project's client.
        position_notifier: Queue position change notifier.
        processor: MergeProcessor loop for this project's queue.
        scheduler: GitLab polling scheduler for this project.
    """

    config: ProjectConfig
    gitlab_client: GitLabClient
    notifier: MRNotifier
    position_notifier: QueuePositionNotifier
    processor: MergeProcessor
    scheduler: QueueScheduler
