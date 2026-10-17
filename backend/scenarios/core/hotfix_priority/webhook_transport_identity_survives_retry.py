from scenarios.contexts.api_helpers import created_test_app
from starlette.testclient import TestClient
from vedro import given, params, scenario, then, when

from gitlab_queue.models.retorts import parse_merge_request_event


@scenario([params("webhook-id"), params("Idempotency-Key")])
async def webhook_transport_identity_survives_retry(identity_header):
    with given("an authenticated webhook with transport identity requiring retry"):
        app, state = created_test_app()
        payload = {
            "object_kind": "merge_request",
            "project": {"id": state.settings.gitlab_project_id},
            "_queue_webhook": {"message_id": "untrusted-body", "event_uuid": "untrusted-body"},
        }
        headers = {
            "X-Gitlab-Token": state.settings.webhook_secret.get_secret_value(),
            identity_header: "stable-message",
            "X-Gitlab-Event-UUID": "operation-chain",
        }

    with when("the existing webhook endpoint stores its retry payload"):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post("/webhooks/gitlab", json=payload, headers=headers)
        saved = state.retry_manager.add_to_retry_queue_calls[-1]["payload"]
        saved["object_attributes"] = {
            "iid": 3,
            "title": "Fix",
            "state": "opened",
            "action": "labeled",
            "source_branch": "fix",
            "target_branch": "main",
            "updated_at": "2026-10-17 08:31:04 UTC",
        }
        replay = parse_merge_request_event(saved)

    with then("retry parsing preserves trusted message identity and source precision"):
        assert response.json()["status"] == "queued_for_retry"
        assert replay.message_id == "stable-message"
        assert replay.event_uuid == "operation-chain"
        assert replay.object_attributes.updated_at_precision_us == 1_000_000
