"""Application configuration loaded from environment variables.

Uses environ-config for type-safe configuration management.
All settings are prefixed with GITLAB_QUEUE_.

Example:
    >>> from gitlab_queue.config import load_settings
    >>> settings = load_settings()
    >>> print(settings.gitlab_url)
    https://gitlab.com
"""

from __future__ import annotations

import hmac
from enum import Enum
from typing import Any
from urllib.parse import urlparse

import environ
from environ import bool_var, var

# Minimum length for JWT secret (256 bits / 8 = 32 bytes, hex-encoded = 64 chars)
JWT_SECRET_MIN_LENGTH = 64


class LogLevel(str, Enum):
    """Valid logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """Valid log output formats."""

    JSON = "json"
    CONSOLE = "console"


class Secret:
    """Wrapper for sensitive values that prevents accidental logging.

    Uses composition instead of inheritance to prevent accidental exposure
    through string operations, slicing, or serialization.

    The secret value is stored in a private attribute and can only be
    accessed through the get_secret_value() method.

    Example:
        >>> token = Secret("glpat-secret-token")
        >>> print(token)
        ***
        >>> print(f"Token: {token}")
        Token: ***
        >>> token.get_secret_value()
        'glpat-secret-token'
    """

    __slots__ = ("_secret_value",)

    def __init__(self, value: str) -> None:
        """Initialize Secret with a string value."""
        object.__setattr__(self, "_secret_value", value)

    def get_secret_value(self) -> str:
        """Return the actual secret value."""
        value: str = object.__getattribute__(self, "_secret_value")
        return value

    def __repr__(self) -> str:
        return "Secret('***')"

    def __str__(self) -> str:
        return "***"

    def __eq__(self, other: object) -> bool:
        """Compare secrets using constant-time comparison to prevent timing attacks."""
        if not isinstance(other, Secret):
            return NotImplemented
        self_value: str = object.__getattribute__(self, "_secret_value")
        other_value: str = object.__getattribute__(other, "_secret_value")
        return hmac.compare_digest(self_value, other_value)

    def __getattribute__(self, name: str) -> Any:
        """Block direct access to the secret value attribute."""
        if name == "_secret_value":
            msg = "Direct access to secret value is not allowed. Use get_secret_value()"
            raise AttributeError(msg)
        return object.__getattribute__(self, name)

    def __hash__(self) -> int:
        return hash(object.__getattribute__(self, "_secret_value"))

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("Secret is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("Secret is immutable")

    def __len__(self) -> int:
        """Return length of secret (safe operation)."""
        return len(object.__getattribute__(self, "_secret_value"))


def _to_secret(value: str) -> Secret:
    """Convert string to Secret."""
    return Secret(value)


def _to_optional_secret(value: str | None) -> Secret | None:
    """Convert string to Secret or return None."""
    if value is None:
        return None
    return Secret(value)


def _to_log_level(value: str) -> LogLevel:
    """Convert string to LogLevel enum."""
    try:
        return LogLevel(value.upper())
    except ValueError:
        valid = ", ".join(level.value for level in LogLevel)
        msg = f"Invalid log level '{value}'. Must be one of: {valid}"
        raise ValueError(msg) from None


def _to_log_format(value: str) -> LogFormat:
    """Convert string to LogFormat enum."""
    try:
        return LogFormat(value.lower())
    except ValueError:
        valid = ", ".join(fmt.value for fmt in LogFormat)
        msg = f"Invalid log format '{value}'. Must be one of: {valid}"
        raise ValueError(msg) from None


def _to_cors_origins_list(value: str) -> list[str]:
    """Convert comma-separated string to list of CORS origins."""
    origins = [origin.strip() for origin in value.split(",") if origin.strip()]
    if not origins:
        msg = "CORS origins cannot be empty"
        raise ValueError(msg)
    return origins


@environ.config(prefix="GITLAB_QUEUE")
class Settings:
    """Application configuration loaded from environment variables.

    All environment variables are prefixed with GITLAB_QUEUE_.

    Required variables (application will not start without these):
        GITLAB_QUEUE_GITLAB_TOKEN: GitLab personal access token with 'api' scope
        GITLAB_QUEUE_GITLAB_PROJECT_ID: GitLab project ID (positive integer)
        GITLAB_QUEUE_JWT_SECRET: Secret key for JWT token signing
            (minimum 64 characters, generate with: openssl rand -hex 64)

    All other variables have sensible defaults and are optional.

    Raises:
        environ.MissingEnvValueError: When loading if required variables are missing.
        ValueError: When loading if type conversion or validation fails.
    """

    # GitLab Connection
    gitlab_url: str = var(default="https://gitlab.com")
    gitlab_token: Secret = var(converter=_to_secret)  # Required
    gitlab_project_id: int = var(converter=int)  # Required

    # Target Branch
    target_branch: str = var(default="master")

    # Queue Labels
    queue_label: str = var(default="merge_queue")
    hotfix_label: str = var(default="hotfix")

    # Timing
    poll_interval_seconds: int = var(default=30, converter=int)
    pipeline_timeout_seconds: int = var(default=7200, converter=int)  # 2 hours
    rebase_timeout_seconds: int = var(default=300, converter=int)  # 5 minutes

    # Retry Logic
    pipeline_retry_count: int = var(default=1, converter=int)
    api_max_retries: int = var(default=5, converter=int)

    # Webhook Retry Queue
    webhook_retry_max_attempts: int = var(default=3, converter=int)
    webhook_retry_base_delay_seconds: int = var(default=30, converter=int)
    webhook_retry_max_delay_seconds: int = var(default=300, converter=int)
    webhook_retry_poll_interval_seconds: int = var(default=10, converter=int)
    webhook_dlq_retention_days: int = var(default=30, converter=int)

    # Database
    database_url: str = var(default="sqlite+aiosqlite:///data/queue.db")

    # GitLab OAuth
    oauth_client_id: str | None = var(default=None)
    oauth_client_secret: Secret | None = var(default=None, converter=_to_optional_secret)
    oauth_redirect_uri: str | None = var(default=None)
    jwt_secret: Secret = var(converter=_to_secret)  # Required
    jwt_expiration_hours: int = var(default=24, converter=int)

    # Webhook Server
    webhook_enabled: bool = bool_var(default=True)
    webhook_host: str = var(default="127.0.0.1")  # Localhost only by default
    webhook_port: int = var(default=8080, converter=int)
    webhook_secret: Secret | None = var(default=None, converter=_to_optional_secret)

    # Dashboard
    dashboard_enabled: bool = bool_var(default=True)
    cors_origins: list[str] = var(
        default="http://localhost:5173", converter=_to_cors_origins_list
    )

    # Monitoring
    log_level: LogLevel = var(default="INFO", converter=_to_log_level)
    log_format: LogFormat = var(default="json", converter=_to_log_format)

def _mask_database_url(self: Settings) -> str:
    """Mask credentials in database URL for safe logging."""
    if "@" in self.database_url:
        try:
            parsed = urlparse(self.database_url)
            if parsed.password:
                masked = self.database_url.replace(f":{parsed.password}@", ":***@")
                return masked
        except (ValueError, AttributeError):
            # URL parsing failed, return unmasked (safe for logging context)
            pass
    return self.database_url


def _settings_repr(self: Settings) -> str:
    """Safe representation that hides sensitive values.

    Note: This function is assigned to Settings.__repr__ after class creation
    because environ-config decorator overwrites the __repr__ method.
    """
    fields = []
    for name in [
        "gitlab_url",
        "gitlab_token",
        "gitlab_project_id",
        "target_branch",
        "queue_label",
        "hotfix_label",
        "poll_interval_seconds",
        "pipeline_timeout_seconds",
        "rebase_timeout_seconds",
        "pipeline_retry_count",
        "api_max_retries",
        "webhook_retry_max_attempts",
        "webhook_retry_base_delay_seconds",
        "webhook_retry_max_delay_seconds",
        "webhook_retry_poll_interval_seconds",
        "webhook_dlq_retention_days",
        "database_url",
        "oauth_client_id",
        "oauth_client_secret",
        "oauth_redirect_uri",
        "jwt_secret",
        "jwt_expiration_hours",
        "webhook_enabled",
        "webhook_host",
        "webhook_port",
        "webhook_secret",
        "dashboard_enabled",
        "cors_origins",
        "log_level",
        "log_format",
    ]:
        value = getattr(self, name)
        if isinstance(value, Secret):
            fields.append(f"{name}=Secret('***')")
        elif name == "database_url":
            fields.append(f"{name}={_mask_database_url(self)!r}")
        elif isinstance(value, Enum):
            fields.append(f"{name}={value.value!r}")
        else:
            fields.append(f"{name}={value!r}")
    return f"Settings({', '.join(fields)})"


# Re-assign __repr__ after class creation because environ-config decorator
# overwrites the __repr__ method defined inside the class.
Settings.__repr__ = _settings_repr  # type: ignore[assignment]


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""


def _validate_settings(settings: Settings) -> None:
    """Validate settings for logical consistency and valid ranges.

    Args:
        settings: The Settings instance to validate.

    Raises:
        ConfigurationError: If any validation fails.
    """
    errors: list[str] = []

    # Validate GitLab URL
    if not settings.gitlab_url.startswith(("http://", "https://")):
        errors.append(
            f"gitlab_url must start with http:// or https://, got: {settings.gitlab_url}"
        )

    # Validate GitLab project ID
    if settings.gitlab_project_id <= 0:
        errors.append(
            f"gitlab_project_id must be a positive integer, got: {settings.gitlab_project_id}"
        )

    # Validate timing values
    if settings.poll_interval_seconds <= 0:
        errors.append(
            f"poll_interval_seconds must be positive, got: {settings.poll_interval_seconds}"
        )

    if settings.pipeline_timeout_seconds <= 0:
        errors.append(
            f"pipeline_timeout_seconds must be positive, got: {settings.pipeline_timeout_seconds}"
        )

    if settings.rebase_timeout_seconds <= 0:
        errors.append(
            f"rebase_timeout_seconds must be positive, got: {settings.rebase_timeout_seconds}"
        )

    # Validate retry counts
    if settings.pipeline_retry_count < 0:
        errors.append(
            f"pipeline_retry_count cannot be negative, got: {settings.pipeline_retry_count}"
        )

    if settings.api_max_retries < 0:
        errors.append(
            f"api_max_retries cannot be negative, got: {settings.api_max_retries}"
        )

    # Validate webhook retry queue settings
    if settings.webhook_retry_max_attempts < 1:
        errors.append(
            f"webhook_retry_max_attempts must be at least 1, got: {settings.webhook_retry_max_attempts}"
        )

    if settings.webhook_retry_base_delay_seconds <= 0:
        errors.append(
            f"webhook_retry_base_delay_seconds must be positive, got: {settings.webhook_retry_base_delay_seconds}"
        )

    if settings.webhook_retry_max_delay_seconds <= 0:
        errors.append(
            f"webhook_retry_max_delay_seconds must be positive, got: {settings.webhook_retry_max_delay_seconds}"
        )

    if settings.webhook_retry_max_delay_seconds < settings.webhook_retry_base_delay_seconds:
        errors.append(
            f"webhook_retry_max_delay_seconds ({settings.webhook_retry_max_delay_seconds}) "
            f"must be >= webhook_retry_base_delay_seconds ({settings.webhook_retry_base_delay_seconds})"
        )

    if settings.webhook_retry_poll_interval_seconds <= 0:
        errors.append(
            f"webhook_retry_poll_interval_seconds must be positive, got: {settings.webhook_retry_poll_interval_seconds}"
        )

    if settings.webhook_dlq_retention_days < 1:
        errors.append(
            f"webhook_dlq_retention_days must be at least 1, got: {settings.webhook_dlq_retention_days}"
        )

    # Validate JWT expiration
    if settings.jwt_expiration_hours <= 0:
        errors.append(
            f"jwt_expiration_hours must be positive, got: {settings.jwt_expiration_hours}"
        )

    # Validate webhook port
    if not (1 <= settings.webhook_port <= 65535):
        errors.append(
            f"webhook_port must be between 1 and 65535, got: {settings.webhook_port}"
        )

    # Validate webhook secret is set when webhooks are enabled
    if settings.webhook_enabled and settings.webhook_secret is None:
        errors.append(
            "webhook_secret is required when webhook_enabled is true. "
            "Set GITLAB_QUEUE_WEBHOOK_SECRET or disable webhooks with GITLAB_QUEUE_WEBHOOK_ENABLED=false"
        )

    # Validate JWT secret length
    jwt_secret_len = len(settings.jwt_secret)
    if jwt_secret_len < JWT_SECRET_MIN_LENGTH:
        errors.append(
            f"jwt_secret must be at least 64 characters (256 bits) for security, "
            f"got {jwt_secret_len} characters. Generate with: openssl rand -hex 64"
        )

    # Validate CORS origins format
    for origin in settings.cors_origins:
        if origin == "*":
            errors.append(
                "Wildcard CORS origin (*) is not allowed for security. "
                "Specify explicit origins."
            )
        elif not origin.startswith(("http://", "https://")):
            errors.append(
                f"Invalid CORS origin '{origin}': must start with http:// or https://"
            )

    if errors:
        raise ConfigurationError(
            "Configuration validation failed:\n  - " + "\n  - ".join(errors)
        )


def load_settings() -> Settings:
    """Load and validate settings from environment variables.

    All environment variables are prefixed with GITLAB_QUEUE_.
    See Settings class docstring for available configuration options.

    Returns:
        Validated Settings instance with all configuration loaded.

    Raises:
        environ.MissingEnvValueError: If a required environment variable
            (GITLAB_TOKEN, GITLAB_PROJECT_ID, JWT_SECRET) is missing.
        ValueError: If type conversion fails.
        ConfigurationError: If validation fails (invalid values, missing
            required secrets when features are enabled, etc.).

    Example:
        >>> import os
        >>> os.environ["GITLAB_QUEUE_GITLAB_TOKEN"] = "glpat-xxx"
        >>> os.environ["GITLAB_QUEUE_GITLAB_PROJECT_ID"] = "12345"
        >>> os.environ["GITLAB_QUEUE_JWT_SECRET"] = "a" * 64
        >>> os.environ["GITLAB_QUEUE_WEBHOOK_SECRET"] = "webhook-secret"
        >>> settings = load_settings()
        >>> settings.gitlab_url
        'https://gitlab.com'
    """
    settings = environ.to_config(Settings)
    _validate_settings(settings)
    return settings


__all__: list[str] = [
    "JWT_SECRET_MIN_LENGTH",
    "ConfigurationError",
    "LogFormat",
    "LogLevel",
    "Secret",
    "Settings",
    "load_settings",
]
