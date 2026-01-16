"""Utility modules for GitLab Queue Bot."""

from gitlab_queue.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    create_circuit_breaker,
)
from gitlab_queue.utils.logging import (
    LogContext,
    configure_logging,
    generate_request_id,
    get_logger,
    mr_iid_ctx,
    operation_ctx,
    request_id_ctx,
    reset_logging,
    timed_operation,
    timed_operation_async,
)
from gitlab_queue.utils.retry import (
    is_retryable_gitlab_error,
    is_retryable_sqlite_error,
    log_after_retry,
    log_before_retry,
    retry_gitlab_api,
    retry_rebase,
    retry_sqlite,
)

__all__: list[str] = [
    "CircuitBreaker",
    "CircuitOpenError",
    "CircuitState",
    "LogContext",
    "configure_logging",
    "create_circuit_breaker",
    "generate_request_id",
    "get_logger",
    "is_retryable_gitlab_error",
    "is_retryable_sqlite_error",
    "log_after_retry",
    "log_before_retry",
    "mr_iid_ctx",
    "operation_ctx",
    "request_id_ctx",
    "reset_logging",
    "retry_gitlab_api",
    "retry_rebase",
    "retry_sqlite",
    "timed_operation",
    "timed_operation_async",
]
