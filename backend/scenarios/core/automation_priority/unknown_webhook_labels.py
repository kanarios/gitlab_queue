from scenarios.fakes import create_mr
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.models.retorts import parse_merge_request_event

from ._helpers import automation_environment


@scenario([params(None), params("dependencies"), params([None]), params([{}])])
async def unusable_full_webhook_labels_cannot_remove_or_demote_the_existing_entry(labels):
    async with automation_environment() as env:
        with given("an automated entry and a webhook whose current full labels are invalid"):
            before = await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue", "dependencies"]))
            raw = {
                "object_kind": "merge_request",
                "project": {"id": 123},
                "object_attributes": {
                    "iid": 3,
                    "title": "MR3",
                    "state": "opened",
                    "action": "update",
                    "source_branch": "feature",
                    "target_branch": "main",
                },
                "labels": labels,
                "changes": {
                    "labels": {"previous": [{"title": "merge_queue"}, {"title": "dependencies"}], "current": labels}
                },
            }

        with when("the public parser and handler receive the unusable authoritative snapshot"):
            with catched(ValueError) as error:
                await env.handler.handle(parse_merge_request_event(raw))
            after = await env.queue.get_queue_item(123, 3)

        with then("validation rejects the message before labels, membership or comments change"):
            assert error.type is ValueError
            assert after == before
            assert env.server.comments == []
