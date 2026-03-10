from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FakeSettings:
    """Lightweight settings stub for processor unit tests.

    Provides all attributes that MergeProcessor reads from Settings,
    with sensible test defaults. No environment variables required.
    """

    queue_label: str = "merge_queue"
    hotfix_label: str = "hotfix"
    target_branch: str = "main"
    stale_mr_warning_hours: int = 24
    poll_interval_seconds: int = 5
    pipeline_poll_interval_seconds: int = 10
    pipeline_timeout_seconds: int = 3600
    rebase_timeout_seconds: int = 600
    merge_timeout_seconds: int = 120
    job_retry_count: int = 1
    rebase_check_interval_seconds: int = 300
    max_rebase_during_testing: int = 3
    post_rebase_pipeline_wait_seconds: int = 60
    rate_limit_critical_threshold: float = 0.95
    webhook_retry_poll_interval_seconds: int = 1
    gitlab_project_id: int = 1
    max_processing_attempts: int = 3
