"""Test that ModelConverter.history_model_to_queue_item preserves project_id."""

from __future__ import annotations

import vedro
from scenarios.fakes import HistoryItemModel

from gitlab_queue.db.repositories import ModelConverter


class Scenario(vedro.Scenario):
    subject = "history model to queue item preserves project_id"

    def given_history_model_with_project_id(self):
        self.history = HistoryItemModel(
            project_id=55555,
            iid=42,
            title="Test MR",
            author_name="User",
            author_username="user",
            status="merged",
            target_branch="master",
            queued_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T01:00:00+00:00",
        )

    def when_model_is_converted(self):
        self.item = ModelConverter.history_model_to_queue_item(self.history)

    def then_project_id_is_preserved(self):
        assert self.item.project_id == 55555

    def and_iid_is_preserved(self):
        assert self.item.mr_iid == 42

    def and_status_is_preserved(self):
        assert self.item.state == "merged"
