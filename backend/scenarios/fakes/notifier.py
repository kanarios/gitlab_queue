from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .models import create_note

if TYPE_CHECKING:
    from gitlab_queue.models.mr import Note


@dataclass
class FakeNotifier:
    pipeline_url_template: str = "https://gitlab.com/pipeline/{pipeline_id}"

    # Call recording
    notify_calls: list[dict[str, Any]] = field(default_factory=list)
    remove_label_calls: list[int] = field(default_factory=list)

    # Cross-fake call order tracking
    call_order_log: list[str] | None = None

    # Error injection
    notify_error: Exception | None = None

    async def notify(self, mr_iid: int, status: str, **context: Any) -> Note:
        if self.notify_error:
            raise self.notify_error
        self.notify_calls.append(
            {
                "mr_iid": mr_iid,
                "status": status,
                **context,
            }
        )
        return create_note()

    async def build_pipeline_url(self, pipeline_id: int) -> str:
        return self.pipeline_url_template.format(pipeline_id=pipeline_id)

    async def remove_queue_label(self, mr_iid: int) -> None:
        self.remove_label_calls.append(mr_iid)
        if self.call_order_log is not None:
            self.call_order_log.append("remove_queue_label")
