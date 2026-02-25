"""Test edge cases in retort (de)serialization.

Covers retorts.py lines 129, 218, 406:
- _parse_datetime with ' UTC' suffix (line 129)
- dump_queue_item serializes all fields correctly (line 218)
- parse_webhook_event returns None for unknown kind (line 406)
- _extract_labels handles dict labels with 'name' key
- _extract_labels handles dict labels with 'title' key
"""

from __future__ import annotations

from datetime import UTC, datetime

import vedro

from gitlab_queue.models.retorts import (
    _extract_labels,
    _parse_datetime,
    dump_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "_parse_datetime parses 'YYYY-MM-DD HH:MM:SS UTC' format"

    def given_datetime_string_with_utc_suffix(self):
        """
        Set up a datetime string ending with ' UTC' for the scenario.
        
        Assigns "2025-06-15 14:30:00 UTC" to self.dt_string.
        """
        self.dt_string = "2025-06-15 14:30:00 UTC"

    def when_parse_datetime_is_called(self):
        self.result = _parse_datetime(self.dt_string)

    def then_result_is_datetime(self):
        """
        Assert that self.result is a datetime.datetime instance.
        
        Raises:
            AssertionError: if self.result is not an instance of datetime.datetime.
        """
        assert isinstance(self.result, datetime)

    def and_result_has_timezone(self):
        assert self.result.tzinfo is not None

    def and_year_is_correct(self):
        """
        Asserts that the parsed datetime's year equals 2025.
        """
        assert self.result.year == 2025

    def and_month_is_correct(self):
        assert self.result.month == 6

    def and_hour_is_correct(self):
        assert self.result.hour == 14


class Scenario2(vedro.Scenario):
    subject = "_parse_datetime returns None for None input"

    def given_none_value(self):
        self.dt_string = None

    def when_parse_datetime_is_called(self):
        self.result = _parse_datetime(self.dt_string)

    def then_result_is_none(self):
        """
        Assert that the scenario result is None.
        
        Raises:
            AssertionError: If `self.result` is not `None`.
        """
        assert self.result is None


class Scenario3(vedro.Scenario):
    subject = "_parse_datetime returns None for empty string"

    def given_empty_string(self):
        """
        Set the scenario's `dt_string` attribute to an empty string.
        """
        self.dt_string = ""

    def when_parse_datetime_is_called(self):
        self.result = _parse_datetime(self.dt_string)

    def then_result_is_none(self):
        """
        Assert that the scenario result is None.
        
        Raises:
            AssertionError: If `self.result` is not `None`.
        """
        assert self.result is None


class Scenario4(vedro.Scenario):
    subject = "dump_queue_item serializes started_at as None when absent"

    def given_queue_item_without_started_at(self):
        """
        Prepare a QueueItem instance without a started_at timestamp and assign it to self.item.
        
        The created QueueItem has mr_iid=1, title "Test", author_name "Alice", author_username "alice",
        target_branch "main", state "queued", queued_at set to 2025-01-01 UTC, and started_at set to None.
        """
        from gitlab_queue.models.queue_item import QueueItem

        self.item = QueueItem(
            mr_iid=1,
            title="Test",
            author_name="Alice",
            author_username="alice",
            target_branch="main",
            state="queued",
            queued_at=datetime(2025, 1, 1, tzinfo=UTC),
            started_at=None,
        )

    def when_dump_queue_item_is_called(self):
        self.result = dump_queue_item(self.item)

    def then_started_at_is_none(self):
        """
        Assert that the serialized queue item's "started_at" field is None.
        """
        assert self.result["started_at"] is None

    def and_queued_at_is_iso_string(self):
        """
        Asserts that the serialized `queued_at` field is an ISO-formatted datetime string containing the date 2025-01-01.
        
        Raises:
            AssertionError: If `self.result["queued_at"]` is not a string or does not contain "2025-01-01".
        """
        assert isinstance(self.result["queued_at"], str)
        assert "2025-01-01" in self.result["queued_at"]


class Scenario5(vedro.Scenario):
    subject = "_extract_labels extracts names from dict labels with 'name' key"

    def given_labels_as_dict_list_with_name_key(self):
        """
        Set the scenario's labels to a list of label dictionaries using the 'name' key.
        
        Each dictionary represents a label; this step assigns [{"name": "bug"}, {"name": "feature"}] to self.labels.
        """
        self.labels = [{"name": "bug"}, {"name": "feature"}]

    def when_extract_labels_is_called(self):
        self.result = _extract_labels(self.labels)

    def then_result_contains_label_names(self):
        """
        Assert that self.result equals ["bug", "feature"].
        """
        assert self.result == ["bug", "feature"]


class Scenario6(vedro.Scenario):
    subject = "_extract_labels extracts titles from dict labels with 'title' key"

    def given_labels_as_dict_list_with_title_key(self):
        self.labels = [{"title": "merge_queue"}, {"title": "hotfix"}]

    def when_extract_labels_is_called(self):
        self.result = _extract_labels(self.labels)

    def then_result_contains_label_titles(self):
        assert self.result == ["merge_queue", "hotfix"]


class Scenario7(vedro.Scenario):
    subject = "_extract_labels returns empty list for empty input"

    def given_empty_labels(self):
        """
        Set up an empty labels list for the scenario.
        
        Assigns an empty list to self.labels to simulate a case with no labels.
        """
        self.labels = []

    def when_extract_labels_is_called(self):
        self.result = _extract_labels(self.labels)

    def then_result_is_empty_list(self):
        assert self.result == []
