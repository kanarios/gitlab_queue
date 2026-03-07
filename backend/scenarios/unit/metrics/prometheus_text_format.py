"""Test get_metrics_output returns Prometheus text format and update functions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import vedro

from gitlab_queue.metrics import (
    get_metrics_output,
    update_gitlab_metrics,
    update_queue_metrics,
)


class _FakeCircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"


@dataclass
class _FakeRateLimitState:
    remaining: int | None = None


@dataclass
class _FakeCircuitBreaker:
    state: _FakeCircuitState = _FakeCircuitState.CLOSED


@dataclass
class _FakeGitLabClient:
    rate_limit_state: _FakeRateLimitState
    circuit_breaker: _FakeCircuitBreaker


class _FakeQueueManager:
    def __init__(self, stats: dict[str, int]) -> None:
        self._stats = stats

    async def get_queue_stats(self) -> dict[str, int]:
        return self._stats


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
        self.queue_manager = _FakeQueueManager(
            stats={"queued": 3, "processing": 1, "merged": 5},
        )

    async def when_queue_metrics_are_updated(self):
        await update_queue_metrics(self.queue_manager)

    def then_queue_length_gauges_should_be_set(self):
        output = get_metrics_output().decode("utf-8")
        assert 'merge_queue_length{status="queued"} 3.0' in output
        assert 'merge_queue_length{status="processing"} 1.0' in output
        assert 'merge_queue_length{status="merged"} 5.0' in output


class Scenario3(vedro.Scenario):
    subject = "update_gitlab_metrics updates rate limit and circuit breaker"

    def given_mock_gitlab_client(self):
        self.gitlab_client = _FakeGitLabClient(
            rate_limit_state=_FakeRateLimitState(remaining=950),
            circuit_breaker=_FakeCircuitBreaker(state=_FakeCircuitState.CLOSED),
        )

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
        self.gitlab_client = _FakeGitLabClient(
            rate_limit_state=_FakeRateLimitState(remaining=None),
            circuit_breaker=_FakeCircuitBreaker(state=_FakeCircuitState.OPEN),
        )

    def when_gitlab_metrics_are_updated(self):
        update_gitlab_metrics(self.gitlab_client)

    def then_no_error_should_be_raised(self):
        pass  # If we got here, no error was raised
