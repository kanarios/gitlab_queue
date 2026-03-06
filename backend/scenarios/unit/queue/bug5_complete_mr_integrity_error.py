"""Test: complete_mr deletes from active table even after IntegrityError on history insert."""

from __future__ import annotations

from datetime import UTC, datetime

import vedro
from sqlalchemy.exc import IntegrityError

from gitlab_queue.core.queue import QueueManager
from scenarios.fakes import FakeDatabase, FakeResult, FakeSession


class Scenario(vedro.Scenario):
    subject = "complete_mr deletes from active table after IntegrityError on history duplicate"

    def given_queue_manager_with_duplicate_history_error(self):
        self.executed_sql: list[str] = []
        self.transaction_count = 0

        # --- Transaction sessions ---
        # First transaction: INSERT to history fails with IntegrityError
        async def first_tx_execute(sql, params=None):
            sql_text = str(sql)
            self.executed_sql.append(sql_text)
            if "INSERT INTO merge_requests_history" in sql_text:
                raise IntegrityError(
                    "INSERT INTO merge_requests_history",
                    params={},
                    orig=Exception("UNIQUE constraint failed: merge_requests_history.iid"),
                )

        first_tx = FakeSession(execute_fn=first_tx_execute)

        # Second transaction: DELETE should succeed
        async def second_tx_execute(sql, params=None):
            sql_text = str(sql)
            self.executed_sql.append(sql_text)

        second_tx = FakeSession(execute_fn=second_tx_execute)

        # --- Session for get_queue_item ---
        row_data = {
            "iid": 42,
            "title": "Test MR",
            "author_name": "Test",
            "author_username": "test",
            "author_avatar": None,
            "status": "merging",
            "is_hotfix": 0,
            "labels": "[]",
            "target_branch": "main",
            "queued_at": datetime.now(UTC).isoformat(),
            "started_at": None,
            "finished_at": None,
            "pipeline_id": None,
            "pipeline_status": None,
            "expected_sha": None,
            "retry_count": 0,
            "last_error": None,
            "stale_warning_sent": 0,
        }

        async def session_execute(sql, params=None):
            return FakeResult(_row_data=row_data)

        read_session = FakeSession(execute_fn=session_execute)

        self.db = FakeDatabase(
            _transaction_sessions=[first_tx, second_tx],
            _session_sessions=[read_session],
        )
        self.qm = QueueManager(db=self.db)

    async def when_complete_mr_is_called(self):
        self.result = await self.qm.complete_mr(42, status="merged")

    def then_result_should_be_false(self):
        assert self.result is False

    def then_delete_should_be_executed_in_second_transaction(self):
        delete_calls = [
            s for s in self.executed_sql if "DELETE FROM merge_requests" in s and "merge_requests_history" not in s
        ]
        assert len(delete_calls) >= 1, f"Expected DELETE from merge_requests, got SQL calls: {self.executed_sql}"

    def and_two_transactions_should_have_been_opened(self):
        assert self.db._transaction_index == 2, f"Expected 2 transactions, got {self.db._transaction_index}"
