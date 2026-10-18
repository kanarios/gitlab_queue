"""Effective queue priority, independent of workflow and author identity."""

import json
from typing import Literal, cast

QueuePriority = Literal["hotfix", "ordinary", "automated"]

PRIORITY_RANK_SQL = "CASE WHEN is_hotfix = 1 THEN 0 WHEN is_automated = 1 THEN 2 ELSE 1 END"


def effective_priority(is_hotfix: bool, is_automated: bool) -> QueuePriority:
    if is_hotfix:
        return "hotfix"
    if is_automated:
        return "automated"
    return "ordinary"


def parse_saved_labels(raw: object) -> list[str] | None:
    """Return a complete saved snapshot, or unknown without rewriting its bytes."""
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return None
    else:
        decoded = raw
    if not isinstance(decoded, list) or not all(isinstance(label, str) for label in decoded):
        return None
    return cast("list[str]", decoded)
