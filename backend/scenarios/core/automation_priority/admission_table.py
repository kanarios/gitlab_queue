from scenarios.core.hotfix_priority._helpers import label_event
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from ._helpers import automation_environment


@scenario(
    [
        params([], ("dependencies", "renovate"), "human", []),
        params(["dependencies"], ("dependencies", "renovate"), "human", []),
        params(["merge_queue"], ("dependencies", "renovate"), "automation-bot", ["ordinary"]),
        params(["merge_queue", "dependencies"], ("dependencies", "renovate"), "human", ["automated"]),
        params(["hotfix"], ("dependencies", "renovate"), "human", ["hotfix"]),
        params(["hotfix", "dependencies"], ("dependencies", "renovate"), "human", ["hotfix"]),
        params(["merge_queue", "hotfix"], ("dependencies", "renovate"), "human", ["hotfix"]),
        params(["merge_queue", "hotfix", "dependencies"], ("dependencies", "renovate"), "human", ["hotfix"]),
        params(["merge_queue", "renovate"], ("dependencies", "renovate"), "human", ["automated"]),
        params(["merge_queue", "обновления"], ("обновления",), "human", ["automated"]),
        params(["merge_queue", "team bot"], ("team bot",), "human", ["automated"]),
        params(["hotfix"], ("hotfix",), "human", ["hotfix"]),
        params(["merge_queue"], ("merge_queue",), "human", ["automated"]),
        params(["merge_queue", "dependencies"], (), "human", ["ordinary"]),
    ]
)
async def admission_triggers_and_effective_priority_are_independent(labels, automation, author, expected):
    async with automation_environment(automation_labels=automation) as env:
        with given("the complete queue/hotfix/automation decision-table input and an independent author"):
            env.server.mrs = [mr_response(3, labels=labels, author_username=author)]
        with when("the real parser and public webhook handle the label event"):
            await env.handler.handle(label_event("labeled", [], labels))
            queue = await env.queue.get_active_queue(123)
        with then("only existing triggers admit exactly one correctly classified incarnation"):
            assert [item.priority for item in queue] == expected
            assert [item.author_username for item in queue] == [author] * len(expected)
            assert [item.labels for item in queue] == [labels] * len(expected)
