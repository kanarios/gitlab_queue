"""Helper functions for health endpoint tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from scenarios.contexts.api_helpers import created_webhook_state

from gitlab_queue.utils.circuit_breaker import CircuitState

if TYPE_CHECKING:
    from gitlab_queue.webhooks.router import WebhookAppState


def create_webhook_state(
    db_connected: bool = True,
    gitlab_circuit_state: CircuitState = CircuitState.CLOSED,
) -> WebhookAppState:
    """Create WebhookAppState with fake dependencies.

    Args:
        db_connected: Whether database should be healthy.
        gitlab_circuit_state: GitLab circuit breaker state.

    Returns:
        WebhookAppState with all dependencies configured.
    """
    return created_webhook_state(
        db_healthy=db_connected,
        gitlab_circuit_state=gitlab_circuit_state,
    )
