import httpx
from scenarios.contexts.api_helpers import created_mock_health, created_test_jwt
from scenarios.core.hotfix_priority._helpers import GitLabServer, queue_services
from scenarios.fakes import create_mr
from vedro import given, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.webhooks.retry_manager import WebhookRetryManager
from gitlab_queue.webhooks.router import WebhookAppState, create_webhook_app

from ._helpers import migrated_storage


@scenario()
async def dashboard_and_dlq_real_api_use_database_and_project_authorization():
    async with migrated_storage() as database, queue_services(QueueManager(database), GitLabServer()) as env:
        with given("real queue/history/retry services and an authenticated single-project API"):
            await env.queue.add_to_queue(123, create_mr(iid=1))
            await env.queue.complete_mr(123, 1, "merged")
            await env.queue.add_to_queue(123, create_mr(iid=2))
            await env.queue.add_to_queue(456, create_mr(iid=1))
            await env.queue.complete_mr(456, 1, "failed")
            manager = WebhookRetryManager(database, max_attempts=1, base_delay_seconds=0)
            source = await manager.add_to_retry_queue("merge_request", {"project": {"id": 123}}, "first", 123)
            await manager.mark_retry_failed(source, "last", 123)
            foreign = await manager.add_to_retry_queue("merge_request", {"project": {"id": 456}}, "first", 456)
            await manager.mark_retry_failed(foreign, "last", 456)
            state = WebhookAppState(
                env.settings,
                database,
                env.gitlab,
                env.queue,
                env.handler.notifier,
                env.handler.position_notifier,
                manager,
                created_mock_health(),
                env.websocket,
            )
            app = create_webhook_app(state)
            headers = {"Authorization": f"Bearer {created_test_jwt(env.settings, project_id=123)}"}

        with when("dashboard, analytics, history and DLQ management routes use real repositories"):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://test", headers=headers
            ) as client:
                stats = await client.get("/api/queue/stats")
                dashboard = await client.get("/api/queue")
                history = await client.get("/api/history")
                summary = await client.get("/api/analytics/summary")
                outcomes = await client.get("/api/analytics/outcomes")
                hourly = await client.get("/api/analytics/hourly")
                reasons = await client.get("/api/analytics/failure-reasons")
                dead = await client.get("/api/dlq")
                entry_id = dead.json()["items"][0]["id"]
                item = await client.get(f"/api/dlq/{entry_id}")
                forbidden = await client.get("/api/projects/456/dlq")
                replay = await client.post(f"/api/dlq/{entry_id}/retry")
                absent = await client.get(f"/api/dlq/{entry_id}")
                await manager.mark_retry_failed(replay.json()["retry_id"], "last", 123)
                new_dead = (await client.get("/api/dlq")).json()["items"][0]["id"]
                deleted = await client.delete(f"/api/dlq/{new_dead}")

        with then("project statistics, persisted feedback and management results are consistent"):
            assert [
                response.status_code
                for response in (
                    stats,
                    dashboard,
                    history,
                    summary,
                    outcomes,
                    hourly,
                    reasons,
                    dead,
                    item,
                    replay,
                    deleted,
                )
            ] == [200] * 11
            assert stats.json()["current"]["total"] == 1
            assert stats.json()["historical"]["merged_count"] == 1
            assert stats.json()["historical"]["failed_count"] == 0
            assert [item["mr_iid"] for item in dashboard.json()["queue"]] == [2]
            assert history.json()["pagination"]["total"] == 1
            assert summary.json()["total_processed"] == 1
            assert dead.json()["stats"]["total_count"] == 1
            assert item.json()["project_id"] == 123
            assert forbidden.status_code == absent.status_code == 404
            assert len(await manager.get_dlq_entries(project_id=456)) == 1
            assert await manager.get_dlq_entries(project_id=123) == []
