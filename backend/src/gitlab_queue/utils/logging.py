"""Structured logging configuration for GitLab Queue Bot.

Provides JSON and console logging formats using structlog with:
- Context variables for request/operation tracking
- Automatic filtering of sensitive data (tokens, secrets)
- Configurable log levels

Example:
    >>> from gitlab_queue.utils.logging import configure_logging, get_logger
    >>> from gitlab_queue.config import LogLevel, LogFormat
    >>> configure_logging(LogLevel.INFO, LogFormat.JSON)
    >>> log = get_logger()
    >>> log.info("Processing MR", mr_iid=42)
"""

from __future__ import annotations

import logging
import re
import sys
import threading
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from structlog.types import EventDict, Processor

    from gitlab_queue.config import LogFormat, LogLevel

# Context variables for request tracking
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
mr_iid_ctx: ContextVar[int | None] = ContextVar("mr_iid", default=None)
operation_ctx: ContextVar[str | None] = ContextVar("operation", default=None)

# Module-level state for cleanup (protected by lock for thread safety)
_logging_configured: bool = False
_logging_lock = threading.Lock()

# Patterns for sensitive data that should be masked
_SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Database URLs with embedded credentials (postgresql://user:pass@host/db)
    (re.compile(r"://([^:/@]+):([^@]+)@", re.IGNORECASE), r"://\1:***@"),
    # GitLab tokens (personal access tokens, project tokens, etc.)
    (re.compile(r"glpat-[a-zA-Z0-9_-]+", re.IGNORECASE), "glpat-***"),
    (re.compile(r"gldt-[a-zA-Z0-9_-]+", re.IGNORECASE), "gldt-***"),
    (re.compile(r"glsoat-[a-zA-Z0-9_-]+", re.IGNORECASE), "glsoat-***"),
    # Generic Bearer tokens
    (re.compile(r"Bearer\s+[a-zA-Z0-9_.-]+", re.IGNORECASE), "Bearer ***"),
    # Private-Token header value (must be before generic token pattern)
    (re.compile(r"(Private-Token):\s*[^\s]+", re.IGNORECASE), r"\1: ***"),
    # Generic API keys and secrets in key=value format
    (re.compile(r"(api[_-]?key|secret|password|auth)[=:]\s*[^\s,}\"']+", re.IGNORECASE), r"\1=***"),
    # Token patterns (but not Private-Token which is handled above)
    (re.compile(r"(?<!Private-)([Tt]oken)[=:]\s*[^\s,}\"']+"), r"\1=***"),
    # JWT tokens (three base64 parts separated by dots)
    (re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"), "***JWT***"),
]


def _mask_sensitive_value(value: str) -> str:
    """Mask sensitive patterns in a string value."""
    result = value
    for pattern, replacement in _SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def _mask_sensitive_data(
    _logger: logging.Logger,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Processor that masks sensitive data in log events.

    Recursively processes strings in the event dictionary to mask
    tokens, secrets, and other sensitive patterns.
    """
    def mask_value(value: Any) -> Any:
        if isinstance(value, str):
            return _mask_sensitive_value(value)
        if isinstance(value, dict):
            return {k: mask_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [mask_value(item) for item in value]
        # Handle Secret wrapper from config
        if hasattr(value, "get_secret_value"):
            return "***"
        return value

    return {key: mask_value(val) for key, val in event_dict.items()}


def _add_context_vars(
    _logger: logging.Logger,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Add context variables to log events if set."""
    request_id = request_id_ctx.get()
    if request_id is not None:
        event_dict["request_id"] = request_id

    mr_iid = mr_iid_ctx.get()
    if mr_iid is not None:
        event_dict["mr_iid"] = mr_iid

    operation = operation_ctx.get()
    if operation is not None:
        event_dict["operation"] = operation

    return event_dict


def _get_shared_processors() -> list[Processor]:
    """Return processors shared between structlog and stdlib logging."""
    return [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _add_context_vars,
        _mask_sensitive_data,
    ]


def _get_json_renderer() -> Processor:
    """Return JSON renderer for production logging."""
    return structlog.processors.JSONRenderer()


def _get_console_renderer() -> Processor:
    """Return colored console renderer for development."""
    return structlog.dev.ConsoleRenderer(
        colors=True,
        exception_formatter=structlog.dev.plain_traceback,
    )


def configure_logging(
    level: LogLevel,
    log_format: LogFormat,
) -> None:
    """Configure structured logging for the application.

    Sets up structlog with appropriate processors for JSON or console output.
    Uses synchronous logging for simplicity and compatibility.

    This function is idempotent - calling it multiple times is safe.

    Args:
        level: Minimum log level to output.
        log_format: Output format (JSON for production, console for development).

    Example:
        >>> from gitlab_queue.config import LogLevel, LogFormat
        >>> configure_logging(LogLevel.DEBUG, LogFormat.CONSOLE)
    """
    global _logging_configured

    # Import here to avoid circular imports: logging.py and config.py are closely
    # coupled, and config.py defines LogLevel/LogFormat enums which are needed by
    # both modules. This late import is intentional and documented.
    from gitlab_queue.config import LogFormat as LF

    with _logging_lock:

        # Choose renderer based on format
        renderer = _get_json_renderer() if log_format == LF.JSON else _get_console_renderer()

        # Configure structlog with stdlib integration
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                *_get_shared_processors(),
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        # Create formatter for stdlib logging
        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=_get_shared_processors(),
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )

        # Create stream handler (direct output, no queue)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.addHandler(stream_handler)
        root_logger.setLevel(level.value)

        # Also configure gitlab_queue logger
        app_logger = logging.getLogger("gitlab_queue")
        app_logger.setLevel(level.value)

        # Suppress noisy third-party loggers
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("uvicorn").setLevel(logging.INFO)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

        _logging_configured = True


def reset_logging() -> None:
    """Reset logging state for testing.

    Clears all context variables and resets configuration flag.
    Useful in tests to ensure clean state between test cases.
    """
    global _logging_configured
    with _logging_lock:
        _logging_configured = False
    request_id_ctx.set(None)
    mr_iid_ctx.set(None)
    operation_ctx.set(None)


def get_logger(name: str = "gitlab_queue") -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name, defaults to 'gitlab_queue'.

    Returns:
        A bound structlog logger that supports structured logging.

    Example:
        >>> log = get_logger()
        >>> log.info("Processing MR", mr_iid=42, status="rebasing")
        >>> log.error("Failed to rebase", mr_iid=42, error="conflict")
    """
    return structlog.stdlib.get_logger(name)


class LogContext:
    """Context manager for setting logging context variables.

    Provides a clean way to add context to all log messages within a scope.
    Context is automatically cleared when exiting the scope.

    Example:
        >>> log = get_logger()
        >>> with LogContext(request_id="abc123", mr_iid=42):
        ...     log.info("Processing started")  # includes request_id and mr_iid
        >>> log.info("Outside context")  # no request_id or mr_iid
    """

    def __init__(
        self,
        *,
        request_id: str | None = None,
        mr_iid: int | None = None,
        operation: str | None = None,
    ) -> None:
        """Initialize context with optional values.

        Args:
            request_id: Unique identifier for the current request/operation.
            mr_iid: Merge request IID being processed.
            operation: Name of the current operation (e.g., 'rebase', 'merge').
        """
        self._request_id = request_id
        self._mr_iid = mr_iid
        self._operation = operation
        self._tokens: list[Any] = []

    def __enter__(self) -> LogContext:
        if self._request_id is not None:
            self._tokens.append(request_id_ctx.set(self._request_id))
        if self._mr_iid is not None:
            self._tokens.append(mr_iid_ctx.set(self._mr_iid))
        if self._operation is not None:
            self._tokens.append(operation_ctx.set(self._operation))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        # Reset in reverse order
        for token in reversed(self._tokens):
            # ContextVar.reset expects the token returned by set()
            # The token's var attribute gives us the ContextVar
            token.var.reset(token)


__all__: list[str] = [
    "LogContext",
    "configure_logging",
    "get_logger",
    "mr_iid_ctx",
    "operation_ctx",
    "request_id_ctx",
    "reset_logging",
]
