from scenarios.core.hotfix_priority._helpers import label_event
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from ._helpers import automation_environment


@scenario([params("Dependencies"), params(" dependencies"), params("dependencies ")])
async def automation_matches_exact_names_without_case_or_whitespace_normalization(label):
    async with automation_environment() as env:
        with given("a differently spelled label that is not configured as automation"):
            env.server.mrs = [mr_response(3, labels=["merge_queue", label])]

        with when("the public handler admits the full GitLab snapshot"):
            await env.handler.handle(label_event("labeled", [], ["merge_queue", label]))
            item = await env.queue.get_queue_item(123, 3)

        with then("the original label spelling remains ordinary"):
            assert item.priority == "ordinary"
            assert item.labels == ["merge_queue", label]
