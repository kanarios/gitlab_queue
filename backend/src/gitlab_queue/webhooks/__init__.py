"""Webhook handling for GitLab Merge Queue Bot.

Provides FastAPI application for receiving GitLab webhooks and health checks,
along with retry queue management for failed webhook events.
"""

from __future__ import annotations

from gitlab_queue.webhooks.handlers import MRWebhookHandler, PipelineWebhookHandler
from gitlab_queue.webhooks.retry_manager import DLQItemNotFoundError, WebhookRetryManager
from gitlab_queue.webhooks.retry_processor import WebhookRetryProcessor, create_retry_processor
from gitlab_queue.webhooks.router import (
    WebhookAppState,
    create_webhook_app,
    dlq_router,
    webhook_router,
)

__all__: list[str] = [
    "DLQItemNotFoundError",
    "MRWebhookHandler",
    "PipelineWebhookHandler",
    "WebhookAppState",
    "WebhookRetryManager",
    "WebhookRetryProcessor",
    "create_retry_processor",
    "create_webhook_app",
    "dlq_router",
    "webhook_router",
]
