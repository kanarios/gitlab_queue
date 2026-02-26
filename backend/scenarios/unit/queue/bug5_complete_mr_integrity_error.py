"""Test: complete_mr deletes from active table even after IntegrityError on history insert."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import vedro
from sqlalchemy.exc import IntegrityError

from gitlab_queue.core.queue import QueueManager


class Scenario(vedro.Scenario):
    subject = "complete_mr deletes from active table after IntegrityError on history duplicate"

    def given_queue_manager_with_duplicate_history_error(self):
        self.db = MagicMock()
        self.qm = QueueManager(db=self.db)

        # Track transaction calls to verify second transaction for DELETE
        self.executed_sql = []
        self.transaction_count = 0

        # First transaction: raise IntegrityError (history duplicate)
        # Second transaction: should execute DELETE
        async def mock_transaction():
            self.transaction_count += 1
            ctx = AsyncMock()

            if self.transaction_count == 1:
                # First transaction: INSERT to history fails with IntegrityError
                async def execute_fail(sql, _params=None):
                    sql_text = str(sql)
                    self.executed_sql.append(sql_text)
                    if "INSERT INTO merge_requests_history" in sql_text:
                        raise IntegrityError(
                            "INSERT INTO merge_requests_history",
                            params={},
                            orig=Exception("UNIQUE constraint failed: merge_requests_history.iid"),
                        )

                ctx.execute = execute_fail
            else:
                # Second transaction: DELETE should succeed
                async def execute_success(sql, _params=None):
                    sql_text = str(sql)
                    self.executed_sql.append(sql_text)

                ctx.execute = execute_success

            return ctx

        # Use async context manager for db.transaction()
        class AsyncCtxManager:
            def __init__(self, coro_func):
                self.coro_func = coro_func

            async def __aenter__(self):
                return await self.coro_func()

            async def __aexit__(self, *args):
                pass

        self.db.transaction = lambda: AsyncCtxManager(mock_transaction)

        # Mock session for get_queue_item
        session_mock = AsyncMock()
        result_mock = MagicMock()
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
        result_mock.mappings.return_value.one_or_none.return_value = row_data
        session_mock.execute = AsyncMock(return_value=result_mock)
        session_mock.commit = AsyncMock()

        class AsyncSessionCtx:
            async def __aenter__(self_inner):
                return session_mock

            async def __aexit__(self_inner, *args):
                pass

        self.db.session = lambda: AsyncSessionCtx()

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
        assert self.transaction_count == 2, f"Expected 2 transactions, got {self.transaction_count}"
