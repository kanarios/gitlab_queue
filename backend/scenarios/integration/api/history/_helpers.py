"""Helper functions for API history tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from scenarios.fakes import HistoryItemModel

if TYPE_CHECKING:
    from gitlab_queue.models.queue_item import QueueItem


def _queue_item_to_history_model(item: QueueItem) -> HistoryItemModel:
    """Convert QueueItem to HistoryItemModel.

    ModelConverter.history_model_to_queue_item expects:
    - queued_at, started_at, finished_at as ISO format strings
    - labels as JSON string
    """
    finished = item.finished_at or datetime.now(UTC)
    return HistoryItemModel(
        iid=item.mr_iid,
        title=item.title,
        author_name=item.author_name,
        author_username=item.author_username,
        author_avatar=item.author_avatar,
        status=item.state,
        is_hotfix=item.is_hotfix,
        labels=json.dumps(item.labels) if item.labels else "[]",
        target_branch=item.target_branch,
        queued_at=item.queued_at.isoformat() if item.queued_at else None,
        started_at=item.started_at.isoformat() if item.started_at else None,
        finished_at=finished.isoformat(),
        pipeline_id=item.pipeline_id,
        pipeline_status=item.pipeline_status,
        failure_reason=item.last_error,
    )
