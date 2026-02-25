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
        """
        Compute and store the current model's string representation.
        
        Sets the instance attribute `self.result` to the result of calling `repr` on `self.model`.
        """
        self.result = repr(self.model)

    def then_repr_should_contain_iid(self):
        assert "iid=42" in self.result

    def and_repr_should_contain_status(self):
        """
        Asserts that the previously computed repr contains the substring "status='queued'".
        """
        assert "status='queued'" in self.result

    def and_repr_should_start_with_class_name(self):
        """
        Assert that the stored `result` string begins with the MergeRequest class prefix.
        
        Raises:
            AssertionError: if `self.result` does not start with "<MergeRequest(".
        """
        assert self.result.startswith("<MergeRequest(")


class Scenario2(vedro.Scenario):
    subject = "WebhookRetryModel repr shows id and event_type"

    def given_webhook_retry_model(self):
        """
        Set up self.model as a WebhookRetryModel pre-populated with representative fields.
        
        Assigns a new WebhookRetryModel to self.model and sets id to 5 and event_type to "merge_request".
        """
        self.model = WebhookRetryModel()
        self.model.id = 5
        self.model.event_type = "merge_request"

    def when_repr_is_called(self):
        """
        Compute and store the current model's string representation.
        
        Sets the instance attribute `self.result` to the result of calling `repr` on `self.model`.
        """
        self.result = repr(self.model)

    def then_repr_should_contain_id(self):
        """
        Asserts that the stored representation string contains the substring "id=5".
        """
        assert "id=5" in self.result

    def and_repr_should_contain_event_type(self):
        """
        Asserts that the previously computed representation contains the substring "event_type='merge_request'".
        """
        assert "event_type='merge_request'" in self.result

    def and_repr_should_start_with_class_name(self):
        """
        Asserts that the previously computed repr string begins with the WebhookRetry class name prefix.
        
        Raises an AssertionError if `self.result` does not start with "<WebhookRetry(".
        """
        assert self.result.startswith("<WebhookRetry(")


class Scenario3(vedro.Scenario):
    subject = "WebhookDLQModel repr shows id and event_type"

    def given_webhook_dlq_model(self):
        """
        Create a WebhookDLQModel instance configured for tests.
        
        Initializes self.model with a WebhookDLQModel and sets:
        - id to 10
        - event_type to "pipeline"
        """
        self.model = WebhookDLQModel()
        self.model.id = 10
        self.model.event_type = "pipeline"

    def when_repr_is_called(self):
        """
        Compute and store the current model's string representation.
        
        Sets the instance attribute `self.result` to the result of calling `repr` on `self.model`.
        """
        self.result = repr(self.model)

    def then_repr_should_contain_id(self):
        """
        Asserts that the captured representation string includes the substring "id=10".
        """
        assert "id=10" in self.result

    def and_repr_should_contain_event_type(self):
        """
        Asserts that the previously stored repr string contains the substring "event_type='pipeline'".
        
        This check verifies that the model's string representation includes the event_type field with value 'pipeline'.
        """
        assert "event_type='pipeline'" in self.result

    def and_repr_should_start_with_class_name(self):
        """
        Asserts that the previously computed representation begins with the WebhookDLQ class prefix.
        
        Raises:
            AssertionError: If the stored representation does not start with "<WebhookDLQ(".
        """
        assert self.result.startswith("<WebhookDLQ(")


class Scenario4(vedro.Scenario):
    subject = "MergeRequestHistoryModel repr shows iid and status"

    def given_history_model(self):
        self.model = MergeRequestHistoryModel()
        self.model.iid = 99
        self.model.status = "merged"

    def when_repr_is_called(self):
        """
        Compute and store the current model's string representation.
        
        Sets the instance attribute `self.result` to the result of calling `repr` on `self.model`.
        """
        self.result = repr(self.model)

    def then_repr_should_contain_iid(self):
        """
        Verifies that the captured representation contains the merge request iid 99.
        
        Asserts that self.result includes the substring "iid=99".
        """
        assert "iid=99" in self.result

    def and_repr_should_contain_status(self):
        assert "status='merged'" in self.result

    def and_repr_should_start_with_class_name(self):
        """
        Asserts that the previously stored representation string begins with the "<MergeRequestHistory(" prefix.
        
        Raises:
            AssertionError: If `self.result` does not start with "<MergeRequestHistory(".
        """
        assert self.result.startswith("<MergeRequestHistory(")


class Scenario5(vedro.Scenario):
    subject = "AnalyticsHourlyModel repr shows timestamp"

    def given_hourly_model(self):
        """
        Create an AnalyticsHourlyModel instance and set its `timestamp` to a representative value for repr testing.
        
        Sets:
            self.model: AnalyticsHourlyModel with `timestamp` = "2026-02-23T10:00:00Z".
        """
        self.model = AnalyticsHourlyModel()
        self.model.timestamp = "2026-02-23T10:00:00Z"

    def when_repr_is_called(self):
        """
        Compute and store the current model's string representation.
        
        Sets the instance attribute `self.result` to the result of calling `repr` on `self.model`.
        """
        self.result = repr(self.model)

    def then_repr_should_contain_timestamp(self):
        """
        Asserts that the stored representation contains the expected ISO-8601 timestamp string.
        
        Raises:
            AssertionError: If "timestamp='2026-02-23T10:00:00Z'" is not present in self.result.
        """
        assert "timestamp='2026-02-23T10:00:00Z'" in self.result

    def and_repr_should_start_with_class_name(self):
        """
        Asserts that the previously stored representation string begins with the AnalyticsHourly class prefix.
        
        Raises:
        	AssertionError: If the stored `self.result` does not start with "<AnalyticsHourly(".
        """
        assert self.result.startswith("<AnalyticsHourly(")


class Scenario6(vedro.Scenario):
    subject = "AnalyticsDailyModel repr shows date"

    def given_daily_model(self):
        """
        Prepare an AnalyticsDailyModel fixture with its date set to 2026-02-23.
        
        Assigns the instantiated model to self.model for use by subsequent scenario steps.
        """
        self.model = AnalyticsDailyModel()
        self.model.date = "2026-02-23"

    def when_repr_is_called(self):
        """
        Compute and store the current model's string representation.
        
        Sets the instance attribute `self.result` to the result of calling `repr` on `self.model`.
        """
        self.result = repr(self.model)

    def then_repr_should_contain_date(self):
        assert "date='2026-02-23'" in self.result

    def and_repr_should_start_with_class_name(self):
        """
        Asserts that the stored repr result starts with the AnalyticsDaily class name prefix.
        
        Raises:
            AssertionError: If the repr string does not start with "<AnalyticsDaily(".
        """
        assert self.result.startswith("<AnalyticsDaily(")
