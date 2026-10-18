from scenarios.contexts.database_backend import isolated_database_url
from scenarios.core.hotfix_priority._helpers import label_event
from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.config import ProjectConfig, Secret
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import run_migrations

from ._helpers import automation_environment


@scenario([params(["hotfix"], ["hotfix", "dependencies"], True), params(["hotfix", "dependencies"], ["hotfix"], False)])
async def automation_changes_under_hotfix_update_metadata_without_splitting_its_fifo(previous, current, automated):
    async with automation_environment() as env:
        with given("an older hotfix followed by another hotfix"):
            original = await env.queue.add_to_queue(123, create_mr(iid=3, labels=previous))
            await env.queue.add_to_queue(123, create_mr(iid=2, labels=["hotfix"]))
        with when("only the automation membership of the older hotfix changes"):
            await env.handler.handle(label_event("update", previous, current))
            changed = await env.queue.get_queue_item(123, 3)
        with then("the fact is fresh but effective band, original identity and feedback remain stable"):
            assert changed.is_automated is automated
            assert changed.priority == "hotfix"
            assert changed.metadata_version == 1
            assert changed.queue_id == original.queue_id
            assert changed.queued_at == original.queued_at
            assert [item.mr_iid for item in await env.queue.get_active_queue(123)] == [3, 2]
            assert env.server.comments == []
            assert env.websocket.broadcast_calls[0]["queue"][0]["priority"] == "hotfix"


@scenario()
async def removing_one_of_two_matching_automation_labels_keeps_the_band_without_false_priority_feedback():
    async with automation_environment() as env:
        with given("an admitted automated MR with two matching labels"):
            original = await env.queue.add_to_queue(
                123, create_mr(iid=3, labels=["merge_queue", "dependencies", "renovate"])
            )
        with when("one matching name is removed and another remains"):
            await env.handler.handle(
                label_event("unlabeled", ["merge_queue", "dependencies", "renovate"], ["merge_queue", "renovate"])
            )
            current = await env.queue.get_queue_item(123, 3)
        with then("only the complete label snapshot changes"):
            assert current.priority == "automated"
            assert current.labels == ["merge_queue", "renovate"]
            assert current.queue_id == original.queue_id
            assert current.metadata_version == 1
            assert env.server.comments == []


@scenario([params("merge_queue"), params("hotfix")])
async def automation_label_cannot_retain_an_entry_after_its_last_admission_trigger_is_removed(trigger):
    async with automation_environment() as env:
        with given("an admitted MR whose automation label will remain after its last trigger is removed"):
            await env.queue.add_to_queue(123, create_mr(iid=3, labels=[trigger, "dependencies"]))
            env.server.mrs = [mr_response(3, labels=["dependencies"])]
        with when("the public webhook removes the last existing admission trigger"):
            await env.handler.handle(label_event("unlabeled", [trigger, "dependencies"], ["dependencies"]))
        with then("the old generation finishes without a replacement or removal of its independent automation label"):
            assert await env.queue.get_queue_item(123, 3) is None
            assert len(await env.queue.get_recent_history(project_id=123)) == 1
            assert env.server.mrs[0]["labels"] == ["dependencies"]


@scenario()
async def config_restart_reclassifies_in_place_and_empty_policy_restores_legacy_fifo():
    async with isolated_database_url() as url:
        await run_migrations(url)
        async with Database(url) as database:
            with given("legacy queue rows whose original identities span two possible automation policies"):
                original = QueueManager(database)
                await original.add_to_queue(123, create_mr(iid=7, labels=["merge_queue", "dependencies"]))
                await original.add_to_queue(123, create_mr(iid=2, labels=["merge_queue", "renovate"]))
                await original.add_to_queue(123, create_mr(iid=9, labels=["merge_queue"]))
                await original.add_to_queue(123, create_mr(iid=1, labels=["hotfix"]), is_hotfix=True)
                identities = {
                    item.mr_iid: (item.queue_id, item.queued_at) for item in await original.get_active_queue(123)
                }
            with when("successive immutable startup policies enable, switch and disable automation"):
                orders, changes, stable = [], [], []
                for labels in ((), ("dependencies",), ("renovate",), ()):
                    queue = QueueManager(
                        database, project_policies={123: ProjectConfig(123, Secret("test"), automation_labels=labels)}
                    )
                    summary = await queue.activate_priorities(123)
                    rows = await queue.get_active_queue(123)
                    orders.append([item.mr_iid for item in rows])
                    changes.append(summary["changed"])
                    stable.append({item.mr_iid: (item.queue_id, item.queued_at) for item in rows})
            with then("each policy uses original-ID FIFO and disabling returns exactly to the old behavior"):
                assert orders == [[1, 7, 2, 9], [1, 2, 9, 7], [1, 7, 9, 2], [1, 7, 2, 9]]
                assert changes == [0, 1, 2, 1]
                assert stable == [identities] * 4
