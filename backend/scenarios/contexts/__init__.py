"""Vedro test contexts for GitLab Queue Bot scenarios.

This module exports all context managers and factory functions used in test scenarios.
Contexts follow the Vedro naming conventions:
- Factories use past tense (e.g., `created_test_app`, `initialized_test_database`)

Example:
    >>> from scenarios.contexts import (
    ...     initialized_test_database,
    ...     created_test_app,
    ... )
"""

from scenarios.contexts.api_helpers import (
    # Aliases for backward compatibility
    create_expired_jwt,
    create_invalid_jwt,
    create_mock_circuit_breaker,
    create_mock_database,
    create_mock_gitlab_client,
    create_mock_health,
    create_mock_notifier,
    create_mock_queue_manager,
    create_mock_retry_manager,
    create_mock_settings,
    create_test_app,
    create_test_app_with_db,
    create_test_history_items,
    create_test_jwt,
    create_test_queue_item,
    create_webhook_state,
    # New names (preferred)
    created_expired_jwt,
    created_invalid_jwt,
    created_mock_circuit_breaker,
    created_mock_database,
    created_mock_gitlab_client,
    created_mock_health,
    created_mock_notifier,
    created_mock_queue_manager,
    created_mock_retry_manager,
    created_mock_settings,
    created_test_app,
    created_test_app_with_db,
    created_test_history_items,
    created_test_jwt,
    created_test_queue_item,
    created_webhook_state,
)
from scenarios.contexts.gitlab_client_factory import (
    MOCK_TRANSPORT_URL,
    TEST_PROJECT_ID,
    # Aliases for backward compatibility
    create_test_client,
    create_test_settings,
    # New names (preferred)
    created_test_client,
    created_test_settings,
)
from scenarios.contexts.sqlite_client import (
    # New names (preferred)
    initialized_test_database,
    opened_test_session,
    started_test_transaction,
    # Aliases for backward compatibility
    test_database,
    test_session,
    test_transaction,
)

__all__ = [
    # GitLab Client Factory
    "MOCK_TRANSPORT_URL",
    "TEST_PROJECT_ID",
    # API Helpers - backward compatibility aliases
    "create_expired_jwt",
    "create_invalid_jwt",
    "create_mock_circuit_breaker",
    "create_mock_database",
    "create_mock_gitlab_client",
    "create_mock_health",
    "create_mock_notifier",
    "create_mock_queue_manager",
    "create_mock_retry_manager",
    "create_mock_settings",
    "create_test_app",
    "create_test_app_with_db",
    "create_test_client",
    "create_test_history_items",
    "create_test_jwt",
    "create_test_queue_item",
    "create_test_settings",
    "create_webhook_state",
    # API Helpers - new names
    "created_expired_jwt",
    "created_invalid_jwt",
    "created_mock_circuit_breaker",
    "created_mock_database",
    "created_mock_gitlab_client",
    "created_mock_health",
    "created_mock_notifier",
    "created_mock_queue_manager",
    "created_mock_retry_manager",
    "created_mock_settings",
    "created_test_app",
    "created_test_app_with_db",
    "created_test_client",
    "created_test_history_items",
    "created_test_jwt",
    "created_test_queue_item",
    "created_test_settings",
    "created_webhook_state",
    # SQLite Client
    "initialized_test_database",
    "opened_test_session",
    "started_test_transaction",
    "test_database",
    "test_session",
    "test_transaction",
]
