from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.models.retorts import parse_merge_request_event

from ._helpers import automation_environment


def webhook_payload(action):
    return {
        "object_kind": "merge_request",
        "project": {"id": 123},
        "object_attributes": {
            "iid": 3,
            "title": "MR3",
            "state": "opened",
            "action": action,
            "source_branch": "feature",
            "target_branch": "main",
        },
    }


@scenario([params("labeled"), params("unlabeled"), params("update")])
async def absent_webhook_snapshot_is_unknown_without_metadata_or_comment_changes(action):
    async with automation_environment() as env:
        with given("an automated MR and a label-bearing webhook with neither labels nor changes.labels"):
            before = await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue", "dependencies"]))
            raw = webhook_payload(action)

        with when("the public parser and handler receive the absent snapshot"):
            with catched(ValueError) as error:
                await env.handler.handle(parse_merge_request_event(raw))
            after = await env.queue.get_queue_item(123, 3)

        with then("unknown labels are rejected instead of being interpreted as an empty full snapshot"):
            assert error.type is ValueError
            assert after == before
            assert env.server.comments == []
            assert env.websocket.broadcast_calls == []


@scenario([params("labeled"), params("unlabeled"), params("update")])
async def valid_changes_current_supplies_the_missing_top_level_snapshot(action):
    async with automation_environment() as env:
        with given("an ordinary MR and a complete label delta without a redundant top-level snapshot"):
            before = await env.queue.add_to_queue(123, create_mr(iid=3))
            raw = webhook_payload(action)
            raw["changes"] = {
                "labels": {
                    "previous": [{"title": "merge_queue"}],
                    "current": [{"title": "merge_queue"}, {"title": "dependencies"}],
                }
            }

        with when("the valid current snapshot reaches the real handler"):
            event = parse_merge_request_event(raw)
            await env.handler.handle(event)
            after = await env.queue.get_queue_item(123, 3)

        with then("the complete fallback updates the same incarnation to automated"):
            assert event.labels == ["merge_queue", "dependencies"]
            assert after.queue_id == before.queue_id
            assert after.queued_at == before.queued_at
            assert after.priority == "automated"
            assert after.labels == ["merge_queue", "dependencies"]


@scenario()
async def explicitly_empty_webhook_labels_remain_a_valid_authoritative_snapshot():
    async with automation_environment() as env:
        with given("an automated MR whose explicit label delta removes its last queue trigger"):
            await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue", "dependencies"]))
            env.server.mrs = [mr_response(3, labels=[])]
            raw = webhook_payload("unlabeled")
            raw["labels"] = []
            raw["changes"] = {
                "labels": {
                    "previous": [{"title": "merge_queue"}, {"title": "dependencies"}],
                    "current": [],
                }
            }

        with when("the public parser and handler process the known empty snapshot"):
            event = parse_merge_request_event(raw)
            await env.handler.handle(event)
            after = await env.queue.get_queue_item(123, 3)
            history = await env.queue.get_recent_history(project_id=123)

        with then("explicit emptiness still removes the MR and retains its final feedback"):
            assert event.labels == []
            assert after is None
            assert len(history) == 1
            assert history[0].state == "removed"
            assert "Removed" in env.server.notes[3]
