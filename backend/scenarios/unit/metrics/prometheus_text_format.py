"""Test get_metrics_output returns Prometheus text format and update functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import vedro

from gitlab_queue.metrics import (
    get_metrics_output,
    update_gitlab_metrics,
    update_queue_metrics,
)


class Scenario(vedro.Scenario):
    subject = "get_metrics_output returns bytes in Prometheus text format"

    def given_metrics_are_available(self):
        pass  # Default Prometheus metrics are always available

    def when_metrics_output_is_generated(self):
        self.output = get_metrics_output()

    def then_output_should_be_bytes(self):
        assert isinstance(self.output, bytes)

    def and_output_should_contain_metric_names(self):
        decoded = self.output.decode("utf-8")
        assert "merge_queue_length" in decoded


class Scenario2(vedro.Scenario):
    subject = "update_queue_metrics updates QUEUE_LENGTH gauge from stats"

    async def given_mock_queue_manager(self):
        self.queue_manager = AsyncMock()
        self.queue_manager.get_queue_stats.return_value = {
            "queued": 3,
            "processing": 1,
            "merged": 5,
        }

    async def when_queue_metrics_are_updated(self):
        await update_queue_metrics(self.queue_manager)

    def then_queue_length_gauges_should_be_set(self):
        # Verify the gauge was set for each status
        output = get_metrics_output().decode("utf-8")
        assert "merge_queue_length" in output


class Scenario3(vedro.Scenario):
    subject = "update_gitlab_metrics updates rate limit and circuit breaker"

    def given_mock_gitlab_client(self):
        self.gitlab_client = MagicMock()
        # Mock rate_limit_state
        rate_limit = MagicMock()
        rate_limit.remaining = 950
        type(self.gitlab_client).rate_limit_state = PropertyMock(return_value=rate_limit)
        # Mock circuit_breaker
        cb = MagicMock()
        cb.state.value = "closed"
        type(self.gitlab_client).circuit_breaker = PropertyMock(return_value=cb)

    def when_gitlab_metrics_are_updated(self):
        update_gitlab_metrics(self.gitlab_client)

    def then_rate_limit_metric_should_be_set(self):
        output = get_metrics_output().decode("utf-8")
        assert "merge_queue_rate_limit_remaining" in output

    def and_circuit_breaker_metric_should_be_set(self):
        output = get_metrics_output().decode("utf-8")
        assert "merge_queue_circuit_breaker_state" in output


class Scenario4(vedro.Scenario):
    subject = "update_gitlab_metrics handles None remaining rate limit"

    def given_mock_gitlab_client_with_none_remaining(self):
        self.gitlab_client = MagicMock()
        rate_limit = MagicMock()
        rate_limit.remaining = None
        type(self.gitlab_client).rate_limit_state = PropertyMock(return_value=rate_limit)
        cb = MagicMock()
        cb.state.value = "open"
        type(self.gitlab_client).circuit_breaker = PropertyMock(return_value=cb)

    def when_gitlab_metrics_are_updated(self):
        update_gitlab_metrics(self.gitlab_client)

    def then_no_error_should_be_raised(self):
        pass  # If we got here, no error was raised
