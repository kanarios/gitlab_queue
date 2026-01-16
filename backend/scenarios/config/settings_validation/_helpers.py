"""Helper functions for settings validation tests."""

from gitlab_queue.config import (
    LogFormat,
    LogLevel,
    Secret,
    Settings,
)


def create_valid_settings(**overrides) -> Settings:
    """Create a valid Settings object with optional overrides.

    Note: environ-config applies converters during __init__, so we pass
    raw string values for fields that have converters (e.g., cors_origins).
    """
    defaults = {
        "gitlab_url": "https://gitlab.com",
        "gitlab_token": Secret("glpat-test-token"),
        "gitlab_project_id": 12345,
        "target_branch": "master",
        "queue_label": "merge_queue",
        "hotfix_label": "hotfix",
        "poll_interval_seconds": 30,
        "pipeline_timeout_seconds": 7200,
        "rebase_timeout_seconds": 300,
        "stale_mr_warning_hours": 24,
        "pipeline_retry_count": 1,
        "api_max_retries": 5,
        "rate_limit_warning_threshold": 0.8,
        "rate_limit_throttle_delay_seconds": 1.0,
        "rate_limit_critical_threshold": 0.95,
        "circuit_breaker_failure_threshold": 5,
        "circuit_breaker_half_open_timeout_seconds": 30,
        "circuit_breaker_success_threshold": 1,
        "webhook_retry_max_attempts": 3,
        "webhook_retry_base_delay_seconds": 30,
        "webhook_retry_max_delay_seconds": 300,
        "webhook_retry_poll_interval_seconds": 10,
        "webhook_dlq_retention_days": 30,
        "database_url": "sqlite+aiosqlite:///data/queue.db",
        "database_retry_base_delay_seconds": 5,
        "database_retry_max_delay_seconds": 60,
        "startup_gitlab_required": False,
        "oauth_client_id": None,
        "oauth_client_secret": None,
        "oauth_redirect_uri": None,
        "jwt_secret": Secret("a" * 64),
        "jwt_expiration_hours": 24,
        "webhook_enabled": True,
        "webhook_host": "127.0.0.1",
        "webhook_port": 8080,
        "webhook_secret": Secret("webhook-secret"),
        "dashboard_enabled": True,
        "cors_origins": ["http://localhost:5173"],
        "log_level": LogLevel.INFO,
        "log_format": LogFormat.JSON,
    }
    defaults.update(overrides)
    return Settings(**defaults)
