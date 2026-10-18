from scenarios.core.hotfix_priority._helpers import label_event
from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, scenario, then, when

from ._helpers import automation_environment


@scenario()
async def adding_automation_label_reorders_the_existing_entry_without_new_admission():
    async with automation_environment() as environment:
        with given("an older ordinary entry followed by another ordinary entry"):
            original = await environment.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue"]))
            await environment.queue.add_to_queue(123, create_mr(iid=2, labels=["merge_queue"]))
            environment.server.mrs = [mr_response(3, labels=["merge_queue", "dependencies"])]

        with when("the public webhook reports only an automation label addition"):
            await environment.handler.handle(label_event("labeled", ["merge_queue"], ["merge_queue", "dependencies"]))
            items = await environment.queue.get_active_queue(123)
            changed = await environment.queue.get_queue_item(123, 3)

        with then("the same incarnation becomes automated behind the ordinary entry"):
            assert [item.mr_iid for item in items] == [2, 3]
            assert changed.priority == "automated"
            assert (changed.queue_id, changed.queued_at) == (original.queue_id, original.queued_at)


@scenario()
async def effective_priority_feedback_changes_even_when_the_waiting_position_does_not():
    async with automation_environment() as environment:
        with given("one ordinary MR whose next full snapshot has an automation label"):
            await environment.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue"]))
            environment.server.mrs = [mr_response(3, labels=["merge_queue", "dependencies"])]

        with when("the public webhook changes its effective band without moving position one"):
            await environment.handler.handle(label_event("labeled", ["merge_queue"], ["merge_queue", "dependencies"]))

        with then("its pinned note describes automation and retains the actual current position"):
            assert "Automated priority" in environment.server.notes[3]
            assert "**Position:** 1 of 1" in environment.server.notes[3]
            assert "Hotfix priority removed" not in environment.server.notes[3]
