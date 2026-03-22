"""Test: get_dashboard_stats queries merge_requests_history table."""

import vedro

from gitlab_queue.core.queue import _SELECT_STATS_WINDOW_BASE_SQL


class Scenario(vedro.Scenario):
    subject = "get dashboard stats queries merge_requests_history table"

    def given_sql_query(self):
        self.sql = _SELECT_STATS_WINDOW_BASE_SQL

    def then_sql_should_query_history_table(self):
        assert "merge_requests_history" in self.sql.lower()
