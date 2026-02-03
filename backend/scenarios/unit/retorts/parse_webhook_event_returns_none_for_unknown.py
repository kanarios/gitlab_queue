"""Test parse_webhook_event() returns None for an unrecognised object_kind."""

from __future__ import annotations

import vedro

from gitlab_queue.models.retorts import parse_webhook_event


class Scenario(vedro.Scenario):
    subject = "parse_webhook_event() returns None for unknown object_kind"

    def given_payload_with_unknown_object_kind(self):
        self.payload = {"object_kind": "unknown_event_type", "project": {"id": 1}}

    def when_parse_webhook_event_is_called(self):
        self.result = parse_webhook_event(self.payload)

    def then_result_is_none(self):
        assert self.result is None

    def and_none_is_returned_when_object_kind_is_missing(self):
        result = parse_webhook_event({})
        assert result is None
