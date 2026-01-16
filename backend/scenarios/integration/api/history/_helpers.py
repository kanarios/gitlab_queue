"""Helper functions for API history tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from gitlab_queue.models.queue_item import QueueItem


def _queue_item_to_history_model(item: QueueItem) -> MagicMock:
    """Convert QueueItem to mock MergeRequestHistoryModel.

    ModelConverter.history_model_to_queue_item expects:
    - queued_at, started_at, finished_at as ISO format strings
    - labels as JSON string
    """
    model = MagicMock()
    model.iid = item.mr_iid
    model.title = item.title
    model.author_name = item.author_name
    model.author_username = item.author_username
    model.author_avatar = item.author_avatar
    model.status = item.state
    model.is_hotfix = item.is_hotfix
    model.labels = json.dumps(item.labels) if item.labels else "[]"
    model.target_branch = item.target_branch
    # Convert datetime objects to ISO format strings
    model.queued_at = item.queued_at.isoformat() if item.queued_at else None
    model.started_at = item.started_at.isoformat() if item.started_at else None
    finished = item.finished_at or datetime.now(UTC)
    model.finished_at = finished.isoformat()
    model.pipeline_id = item.pipeline_id
    model.pipeline_status = item.pipeline_status
    model.failure_reason = item.last_error
    return model
