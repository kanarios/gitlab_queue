"""Test health endpoint version reporting.

Covers health.py lines 76, 128, 167:
- ApplicationHealth.mode returns correct mode for different states
- ApplicationHealth.is_ready checks database and webhook_server
- ApplicationHealth.to_dict includes all required fields
- GitLabHealth.from_circuit_breaker maps states correctly
"""

from __future__ import annotations

import vedro

from gitlab_queue.health import (
    ApplicationHealth,
    ApplicationMode,
    ComponentStatus,
    GitLabHealth,
)
from gitlab_queue.utils.circuit_breaker import CircuitBreaker, CircuitState


class Scenario(vedro.Scenario):
    subject = "ApplicationHealth.mode returns UNHEALTHY when database is not healthy"

    def given_health_with_unhealthy_database(self):
        self.health = ApplicationHealth()
        self.health.database = ComponentStatus.UNHEALTHY
        self.health.gitlab = None

    def when_mode_is_checked(self):
        self.mode = self.health.mode

    def then_mode_is_unhealthy(self):
        assert self.mode == ApplicationMode.UNHEALTHY


class Scenario2(vedro.Scenario):
    subject = "ApplicationHealth.mode returns DEGRADED when GitLab is unhealthy but DB is OK"

    def given_health_with_unhealthy_gitlab(self):
        self.health = ApplicationHealth()
        self.health.database = ComponentStatus.HEALTHY
        self.health.gitlab = GitLabHealth(
            status=ComponentStatus.UNHEALTHY,
            circuit_state="open",
            failure_count=5,
        )

    def when_mode_is_checked(self):
        self.mode = self.health.mode

    def then_mode_is_degraded(self):
        assert self.mode == ApplicationMode.DEGRADED


class Scenario3(vedro.Scenario):
    subject = "ApplicationHealth.mode returns NORMAL when all components are healthy"

    def given_fully_healthy_state(self):
        self.health = ApplicationHealth()
        self.health.database = ComponentStatus.HEALTHY
        self.health.gitlab = GitLabHealth(
            status=ComponentStatus.HEALTHY,
            circuit_state="closed",
            failure_count=0,
        )
        self.health.processor_running = True
        self.health.webhook_server_running = True

    def when_mode_is_checked(self):
        self.mode = self.health.mode

    def then_mode_is_normal(self):
        assert self.mode == ApplicationMode.NORMAL


class Scenario4(vedro.Scenario):
    subject = "ApplicationHealth.is_ready is False when webhook_server is not running"

    def given_health_with_stopped_webhook_server(self):
        self.health = ApplicationHealth()
        self.health.database = ComponentStatus.HEALTHY
        self.health.webhook_server_running = False

    def when_is_ready_is_checked(self):
        self.ready = self.health.is_ready

    def then_ready_is_false(self):
        assert self.ready is False


class Scenario5(vedro.Scenario):
    subject = "ApplicationHealth.to_dict includes gitlab unknown status when gitlab is None"

    def given_health_without_gitlab(self):
        self.health = ApplicationHealth()
        self.health.database = ComponentStatus.HEALTHY
        self.health.webhook_server_running = True
        self.health.gitlab = None

    def when_to_dict_is_called(self):
        self.result = self.health.to_dict()

    def then_gitlab_status_is_unknown(self):
        assert self.result["gitlab"]["status"] == "unknown"

    def and_mode_is_present(self):
        assert "mode" in self.result

    def and_is_ready_is_present(self):
        assert "is_ready" in self.result

    def and_database_is_present(self):
        assert "database" in self.result


class Scenario6(vedro.Scenario):
    subject = "GitLabHealth.from_circuit_breaker maps HALF_OPEN to DEGRADED"

    def given_half_open_circuit_breaker(self):
        self.cb = CircuitBreaker(failure_threshold=5, half_open_timeout=30.0)
        self.cb._state = CircuitState.HALF_OPEN
        self.cb._failure_count = 3

    def when_from_circuit_breaker_is_called(self):
        self.gitlab_health = GitLabHealth.from_circuit_breaker(self.cb)

    def then_status_is_degraded(self):
        assert self.gitlab_health.status == ComponentStatus.DEGRADED

    def and_circuit_state_is_half_open(self):
        assert self.gitlab_health.circuit_state == "half_open"


class Scenario7(vedro.Scenario):
    subject = "GitLabHealth.to_dict includes all required fields"

    def given_gitlab_health(self):
        self.gitlab_health = GitLabHealth(
            status=ComponentStatus.HEALTHY,
            circuit_state="closed",
            failure_count=0,
            retry_after_seconds=None,
        )

    def when_to_dict_is_called(self):
        self.result = self.gitlab_health.to_dict()

    def then_result_contains_status(self):
        assert self.result["status"] == "healthy"

    def and_result_contains_circuit_state(self):
        assert self.result["circuit_state"] == "closed"

    def and_result_contains_failure_count(self):
        assert self.result["failure_count"] == 0

    def and_result_contains_last_checked(self):
        assert "last_checked" in self.result
