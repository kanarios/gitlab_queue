"""Test retorts parsing functions handle edge cases and alternative formats.

Covers:
- _parse_datetime with Z-suffix ISO string (line 129)
- load_queue_item with ISO string dates and JSON string labels (lines 246-261)
- parse_note_event with and without merge_request field (lines 370-374)
"""

from __future__ import annotations

from datetime import UTC

import vedro

from gitlab_queue.models.retorts import load_queue_item, parse_note_event, parse_pipeline_event


class Scenario(vedro.Scenario):
    subject = "load_queue_item() parses ISO string dates and JSON string labels correctly"

    def given_queue_item_data_with_string_dates_and_string_labels(self):
        """
        Set up self.data with a queue-item payload containing ISO-8601 date strings and JSON-encoded labels.

        The payload emulates a queued merge request entry with fields: mr_iid, title, author_name, author_username, target_branch, state, queued_at and started_at as ISO-8601 strings with timezone, and labels as a JSON-encoded string '["merge_queue", "hotfix"]'.
        """
        self.data = {
            "mr_iid": 10,
            "title": "Fix bug",
            "author_name": "Alice",
            "author_username": "alice",
            "target_branch": "main",
            "state": "queued",
            "queued_at": "2025-01-15T10:00:00+00:00",
            "started_at": "2025-01-15T10:05:00+00:00",
            "labels": '["merge_queue", "hotfix"]',
        }

    def when_load_queue_item_is_called(self):
        self.item = load_queue_item(self.data)

    def then_queued_at_is_parsed_as_datetime(self):
        """
        Verify queued_at was parsed as a date-time value.

        Asserts that self.item.queued_at is an instance of datetime.
        """
        from datetime import datetime

        assert isinstance(self.item.queued_at, datetime)

    def and_started_at_is_parsed_as_datetime(self):
        from datetime import datetime

        assert isinstance(self.item.started_at, datetime)

    def and_labels_are_parsed_from_json_string(self):
        assert self.item.labels == ["merge_queue", "hotfix"]

    def and_mr_iid_is_correct(self):
        assert self.item.mr_iid == 10


class Scenario2(vedro.Scenario):
    subject = "load_queue_item() handles empty string labels as empty list"

    def given_queue_item_data_with_empty_string_labels(self):
        self.data = {
            "mr_iid": 11,
            "title": "Another fix",
            "author_name": "Bob",
            "author_username": "bob",
            "target_branch": "main",
            "state": "queued",
            "queued_at": "2025-01-15T10:00:00+00:00",
            "labels": "",
        }

    def when_load_queue_item_is_called(self):
        self.item = load_queue_item(self.data)

    def then_labels_are_empty_list(self):
        assert self.item.labels == []


class Scenario3(vedro.Scenario):
    subject = "parse_pipeline_event() parses created_at with Z suffix via _parse_datetime"

    def given_pipeline_event_payload_with_z_suffix_timestamp(self):
        """
        Set up a pipeline webhook payload whose `created_at` timestamp uses a 'Z' (UTC) suffix.

        Initializes self.payload with a pipeline event dict containing project id, object_attributes including id 200 and created_at "2025-06-01T12:00:00Z", and a null merge_request to exercise parsing of Z-suffixed timestamps.
        """
        self.payload = {
            "object_kind": "pipeline",
            "project": {"id": 5},
            "object_attributes": {
                "id": 200,
                "status": "success",
                "sha": "abc123",
                "ref": "main",
                "url": "https://gitlab.example.com/pipelines/200",
                "created_at": "2025-06-01T12:00:00Z",
            },
            "merge_request": None,
        }

    def when_parse_pipeline_event_is_called(self):
        self.event = parse_pipeline_event(self.payload)

    def then_created_at_is_parsed_correctly(self):
        from datetime import datetime

        assert isinstance(self.event.object_attributes.created_at, datetime)
        assert self.event.object_attributes.created_at.tzinfo == UTC

    def and_pipeline_id_is_correct(self):
        assert self.event.object_attributes.id == 200


class Scenario4(vedro.Scenario):
    subject = "parse_note_event() parses note webhook payload without merge_request"

    def given_note_event_payload_without_merge_request(self):
        self.payload = {
            "object_kind": "note",
            "event_type": "note",
            "project": {"id": 7},
            "user": {"id": 42, "name": "Alice", "username": "alice"},
            "object_attributes": {
                "id": 301,
                "note": "LGTM!",
                "noteable_type": "MergeRequest",
            },
        }

    def when_parse_note_event_is_called(self):
        """
        Parse the scenario's note webhook payload into an event object and store it on self.event.

        Calls parse_note_event with self.payload and assigns the resulting parsed event to the instance attribute `event`.
        """
        self.event = parse_note_event(self.payload)

    def then_note_id_is_correct(self):
        """
        Verify that the parsed note event's `note_id` equals 301.

        Raises:
            AssertionError: If `self.event.note_id` is not 301.
        """
        assert self.event.note_id == 301

    def and_merge_request_iid_is_none(self):
        assert self.event.merge_request_iid is None

    def and_user_data_is_parsed(self):
        assert self.event.user_id == 42
        assert self.event.user_name == "Alice"
        assert self.event.user_username == "alice"


class Scenario5(vedro.Scenario):
    subject = "parse_note_event() parses note webhook payload with merge_request"

    def given_note_event_payload_with_merge_request(self):
        """
        Prepare a note-event payload on self.payload that includes an associated merge request.

        Sets self.payload to a dictionary representing a GitLab note webhook where the noteable is a MergeRequest, containing user info, object_attributes with id and note body, and a merge_request field with `iid` 55.
        """
        self.payload = {
            "object_kind": "note",
            "event_type": "note",
            "project": {"id": 7},
            "user": {"id": 42, "name": "Alice", "username": "alice"},
            "object_attributes": {
                "id": 302,
                "note": "Approved.",
                "noteable_type": "MergeRequest",
            },
            "merge_request": {"iid": 55},
        }

    def when_parse_note_event_is_called(self):
        """
        Parse the scenario's note webhook payload into an event object and store it on self.event.

        Calls parse_note_event with self.payload and assigns the resulting parsed event to the instance attribute `event`.
        """
        self.event = parse_note_event(self.payload)

    def then_merge_request_iid_is_set(self):
        """
        Asserts that the parsed event contains the expected merge request IID of 55.

        This verification checks that the event's `merge_request_iid` field equals 55.
        """
        assert self.event.merge_request_iid == 55

    def and_note_body_is_correct(self):
        assert self.event.note_body == "Approved."
