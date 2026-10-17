import asyncio

from scenarios.fakes import create_mr
from vedro import given, scenario, then, when

from ._helpers import queue_environment


@scenario()
async def metadata_update_has_one_owner():
    async with queue_environment() as env:
        with given("two different metadata updates based on the same queue revision"):
            original = await env.queue.add_to_queue(123, create_mr(iid=3))
            revision = (original.queue_id, original.metadata_version)

        with when("both updates atomically compare and write that revision"):
            results = await asyncio.gather(
                env.queue.update_hotfix_status(123, 3, True, ["merge_queue", "hotfix"], expected_revision=revision),
                env.queue.update_hotfix_status(123, 3, False, ["merge_queue", "reviewed"], expected_revision=revision),
            )

        with then("only one writer owns the change"):
            assert sorted(results) == [False, True]
            item = await env.queue.get_queue_item(123, 3)
            assert item.metadata_version == 1
