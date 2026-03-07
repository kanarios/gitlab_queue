"""Integration test scenarios for webhook pipeline events.

Tests PipelineWebhookHandler with FakeGitLabClient + FakeQueueManager + FakeNotifier
instead of real Database + GitLabMockTransport.
"""

from __future__ import annotations

import asyncio

from scenarios.fakes import (
    FakeCurrentState,
    FakeNotifier,
    FakeStateMachine,
    FakeStateMachineFactory,
)
from scenarios.webhooks.pipeline_webhook._helpers import (
    create_gitlab_client_with_transport,
    create_mock_queue_manager,
    create_mock_settings,
    create_pipeline_event,
    create_queue_item_in_state,
)
from vedro import given, scenario, then, when

from gitlab_queue.webhooks.handlers import PipelineWebhookHandler


@scenario()
async def webhook_pipeline_success_triggers_merge():
    """Test that pipeline success webhook triggers state machine transition."""

    with given("MR in testing state and pipeline success event"):
        settings = create_mock_settings()
        gitlab_client, _transport = create_gitlab_client_with_transport()
        queue_manager = create_mock_queue_manager()

        item = create_queue_item_in_state("testing", mr_iid=200)
        queue_manager.add_item(item)

        notifier = FakeNotifier()
        fake_sm = FakeStateMachine(current_state=FakeCurrentState(id="testing"))
        sm_factory = FakeStateMachineFactory(state_machine=fake_sm)

        handler = PipelineWebhookHandler(
            settings=settings,
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            notifier=notifier,
            state_machine_factory=sm_factory,
        )
        event = create_pipeline_event(mr_iid=200, status="success")

    with when("pipeline success event is handled"):
        await handler.handle(event)

    with then("state machine pipeline_success is triggered"):
        assert len(fake_sm.pipeline_success_calls) == 1

    await gitlab_client.close()


@scenario()
async def webhook_pipeline_failure_triggers_retry():
    """Test that pipeline failure webhook marks MR for retry."""

    with given("MR in testing state and pipeline failure event"):
        settings = create_mock_settings()
        gitlab_client, _transport = create_gitlab_client_with_transport()
        queue_manager = create_mock_queue_manager()

        item = create_queue_item_in_state("testing", retry_count=0, mr_iid=201)
        queue_manager.add_item(item)

        handler = PipelineWebhookHandler(
            settings=settings,
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            notifier=FakeNotifier(),
        )
        event = create_pipeline_event(mr_iid=201, status="failed")

    with when("pipeline failure event is handled"):
        await handler.handle(event)

    with then("MR is marked with pipeline_status=failed"):
        assert len(queue_manager.update_state_calls) == 1
        call = queue_manager.update_state_calls[0]
        assert call["mr_iid"] == 201
        assert call["state"] == "testing"
        assert call["pipeline_status"] == "failed"

    await gitlab_client.close()


@scenario()
async def webhook_concurrent_pipeline_events():
    """Test handling of concurrent pipeline events for same MR."""

    with given("MR in testing state and multiple concurrent pipeline events"):
        settings = create_mock_settings()
        gitlab_client, _transport = create_gitlab_client_with_transport()
        queue_manager = create_mock_queue_manager()

        success_event = create_pipeline_event(mr_iid=202, status="success")
        correct_sha = success_event.object_attributes.sha

        item = create_queue_item_in_state("testing", mr_iid=202)
        item.expected_sha = correct_sha
        queue_manager.add_item(item)

        fake_sm = FakeStateMachine(current_state=FakeCurrentState(id="testing"))
        sm_factory = FakeStateMachineFactory(state_machine=fake_sm)

        handler = PipelineWebhookHandler(
            settings=settings,
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            notifier=FakeNotifier(),
            state_machine_factory=sm_factory,
        )

        events = [
            create_pipeline_event(mr_iid=202, status="running"),
            success_event,
            create_pipeline_event(mr_iid=202, status="failed", sha="wrong_sha"),
        ]

    with when("multiple pipeline events are handled concurrently"):
        tasks = [handler.handle(e) for e in events]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    with then("no exceptions occur"):
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Unexpected exceptions: {exceptions}"

    with then("success event triggers pipeline_success transition"):
        assert len(fake_sm.pipeline_success_calls) == 1
        assert fake_sm.current_state.id == "merging"

    with then("stale failed event with wrong SHA is filtered out"):
        assert len(fake_sm.pipeline_failed_calls) == 0

    await gitlab_client.close()


@scenario()
async def webhook_pipeline_canceled_handling():
    """Test handling of canceled pipeline webhooks."""

    with given("MR in testing state and canceled pipeline event"):
        settings = create_mock_settings()
        gitlab_client, _transport = create_gitlab_client_with_transport()
        queue_manager = create_mock_queue_manager()

        item = create_queue_item_in_state("testing", mr_iid=203)
        queue_manager.add_item(item)

        handler = PipelineWebhookHandler(
            settings=settings,
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            notifier=FakeNotifier(),
        )
        event = create_pipeline_event(mr_iid=203, status="canceled")

    with when("canceled pipeline event is handled"):
        await handler.handle(event)

    with then("MR is marked with pipeline_status=failed"):
        assert len(queue_manager.update_state_calls) == 1
        call = queue_manager.update_state_calls[0]
        assert call["mr_iid"] == 203
        assert call["state"] == "testing"
        assert call["pipeline_status"] == "failed"

    await gitlab_client.close()


__all__ = [
    "webhook_concurrent_pipeline_events",
    "webhook_pipeline_canceled_handling",
    "webhook_pipeline_failure_triggers_retry",
    "webhook_pipeline_success_triggers_merge",
]
