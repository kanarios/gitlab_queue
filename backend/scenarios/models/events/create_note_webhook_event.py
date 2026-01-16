"""Unit tests for webhook event models."""

import vedro

from gitlab_queue.models.events import NoteEvent


class Scenario(vedro.Scenario):
    subject = "create note webhook event"

    def when_note_event_is_created(self):
        self.event = NoteEvent(
            object_kind="note",
            event_type="note",
            project_id=42,
            user_id=1,
            user_name="John Doe",
            user_username="johndoe",
            note_id=5000,
            note_body="LGTM!",
            noteable_type="MergeRequest",
            merge_request_iid=123,
        )

    def then_it_should_have_correct_fields(self):
        assert self.event.object_kind == "note"
        assert self.event.note_id == 5000
        assert self.event.note_body == "LGTM!"
        assert self.event.noteable_type == "MergeRequest"
        assert self.event.merge_request_iid == 123
