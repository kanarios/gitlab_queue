"""Test parse_webhook_event() returns None when object_kind is missing."""

from __future__ import annotations

import vedro

from gitlab_queue.models.retorts import parse_webhook_event


class Scenario(vedro.Scenario):
    subject = "parse_webhook_event() returns None when object_kind is missing"

    def given_payload_without_object_kind(self):
        self.payload = {}

    def when_parse_webhook_event_is_called(self):
        self.result = parse_webhook_event(self.payload)

    def then_result_is_none(self):
        assert self.result is None
