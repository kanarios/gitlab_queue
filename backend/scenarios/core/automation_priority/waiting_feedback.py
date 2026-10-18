from dataclasses import replace

from scenarios.core.hotfix_priority._helpers import label_event
from scenarios.transports.responses import mr_response
from vedro import given, scenario, then, when

from ._helpers import automation_environment


@scenario()
async def initial_and_displaced_automation_comments_explain_the_current_band():
    async with automation_environment() as env:
        with given("an automated MR admitted through the public webhook"):
            env.server.mrs = [mr_response(3, labels=["merge_queue", "dependencies"])]
            await env.handler.handle(label_event("labeled", [], ["merge_queue", "dependencies"]))
            initial_note = env.server.notes[3]

        with when("a later ordinary MR is inserted ahead of the automated waiter"):
            env.server.mrs.append(mr_response(2, labels=["merge_queue"]))
            event = label_event("labeled", [], ["merge_queue"])
            await env.handler.handle(replace(event, object_attributes=replace(event.object_attributes, iid=2)))

        with then("both notes explain automation and actual positions without claiming a completed MR"):
            assert "Automated priority" in initial_note
            assert "**Position:** 1 of 1" in initial_note
            assert "Automated priority" in env.server.notes[3]
            assert "**Position:** 2 of 2" in env.server.notes[3]
            assert "added ahead" in env.server.notes[3]
            assert "MRs ahead were processed" not in env.server.notes[3]
            assert "Ordinary priority" in env.server.notes[2]
