"""Test __repr__ methods of DB models."""

from __future__ import annotations

import vedro

from gitlab_queue.db.models import (
    AnalyticsDailyModel,
    AnalyticsHourlyModel,
    MergeRequestHistoryModel,
    MergeRequestModel,
    WebhookDLQModel,
    WebhookRetryModel,
)


class Scenario(vedro.Scenario):
    subject = "MergeRequestModel repr shows iid and status"

    def given_merge_request_model(self):
        self.model = MergeRequestModel()
        self.model.iid = 42
        self.model.status = "queued"

    def when_repr_is_called(self):
        self.result = repr(self.model)

    def then_repr_should_contain_iid(self):
        assert "iid=42" in self.result

    def and_repr_should_contain_status(self):
        assert "status='queued'" in self.result

    def and_repr_should_start_with_class_name(self):
        assert self.result.startswith("<MergeRequest(")


class Scenario2(vedro.Scenario):
    subject = "WebhookRetryModel repr shows id and event_type"

    def given_webhook_retry_model(self):
        self.model = WebhookRetryModel()
        self.model.id = 5
        self.model.event_type = "merge_request"

    def when_repr_is_called(self):
        self.result = repr(self.model)

    def then_repr_should_contain_id(self):
        assert "id=5" in self.result

    def and_repr_should_contain_event_type(self):
        assert "event_type='merge_request'" in self.result

    def and_repr_should_start_with_class_name(self):
        assert self.result.startswith("<WebhookRetry(")


class Scenario3(vedro.Scenario):
    subject = "WebhookDLQModel repr shows id and event_type"

    def given_webhook_dlq_model(self):
        self.model = WebhookDLQModel()
        self.model.id = 10
        self.model.event_type = "pipeline"

    def when_repr_is_called(self):
        self.result = repr(self.model)

    def then_repr_should_contain_id(self):
        assert "id=10" in self.result

    def and_repr_should_contain_event_type(self):
        assert "event_type='pipeline'" in self.result

    def and_repr_should_start_with_class_name(self):
        assert self.result.startswith("<WebhookDLQ(")


class Scenario4(vedro.Scenario):
    subject = "MergeRequestHistoryModel repr shows iid and status"

    def given_history_model(self):
        self.model = MergeRequestHistoryModel()
        self.model.iid = 99
        self.model.status = "merged"

    def when_repr_is_called(self):
        self.result = repr(self.model)

    def then_repr_should_contain_iid(self):
        assert "iid=99" in self.result

    def and_repr_should_contain_status(self):
        assert "status='merged'" in self.result

    def and_repr_should_start_with_class_name(self):
        assert self.result.startswith("<MergeRequestHistory(")


class Scenario5(vedro.Scenario):
    subject = "AnalyticsHourlyModel repr shows timestamp"

    def given_hourly_model(self):
        self.model = AnalyticsHourlyModel()
        self.model.timestamp = "2026-02-23T10:00:00Z"

    def when_repr_is_called(self):
        self.result = repr(self.model)

    def then_repr_should_contain_timestamp(self):
        assert "timestamp='2026-02-23T10:00:00Z'" in self.result

    def and_repr_should_start_with_class_name(self):
        assert self.result.startswith("<AnalyticsHourly(")


class Scenario6(vedro.Scenario):
    subject = "AnalyticsDailyModel repr shows date"

    def given_daily_model(self):
        self.model = AnalyticsDailyModel()
        self.model.date = "2026-02-23"

    def when_repr_is_called(self):
        self.result = repr(self.model)

    def then_repr_should_contain_date(self):
        assert "date='2026-02-23'" in self.result

    def and_repr_should_start_with_class_name(self):
        assert self.result.startswith("<AnalyticsDaily(")
