import asyncio
from contextlib import suppress
from dataclasses import dataclass, field

import httpx
from scenarios.core.hotfix_priority._helpers import GitLabServer
from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, scenario, then, when

from gitlab_queue.core.processor import MergeProcessor

from ._helpers import automation_environment


@dataclass
class PartialStartupServer(GitLabServer):
    point_reads: int = 0
    workflow_read: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)

    async def respond(self, request):
        if request.method == "GET" and request.url.path.endswith("/merge_requests/3"):
            self.point_reads += 1
            if self.point_reads == 2:
                self.workflow_read.set()
                await self.release.wait()
        return await super().respond(request)

    def _response(self, request):
        if request.url.path.endswith("/merge_requests"):
            if request.url.params["labels"] == "merge_queue":
                return httpx.Response(
                    200, json=[mr_response(55, labels=["merge_queue"])], headers={"x-next-page": "invalid"}
                )
            return httpx.Response(200, json=[mr_response(3, labels=["hotfix"])], headers={"x-next-page": ""})
        return super()._response(request)


@scenario()
async def processor_startup_does_not_use_the_successful_half_of_an_incomplete_label_union():
    server = PartialStartupServer(mrs=[mr_response(3, labels=["hotfix", "dependencies"])])
    async with automation_environment(server_factory=lambda: server) as environment:
        with given("a saved hotfix automation fact and a startup discovery that fails only its queue-label half"):
            before = await environment.queue.add_to_queue(123, create_mr(iid=3, labels=["hotfix", "dependencies"]))
            processor = MergeProcessor(
                environment.gitlab,
                environment.queue,
                environment.handler.notifier,
                environment.settings,
                environment.handler.position_notifier,
            )

        with when("the real processor completes startup and pauses before workflow verification"):
            running = asyncio.create_task(processor.run())
            try:
                await asyncio.wait_for(server.workflow_read.wait(), 5)
                after = await environment.queue.get_queue_item(123, 3)
            finally:
                processor.request_shutdown()
                running.cancel()
                with suppress(asyncio.CancelledError):
                    await running
                server.release.set()

        with then("the full saved classification and metadata revision remain untouched by the partial union"):
            assert after == before
            assert after.is_automated is True
