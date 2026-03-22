"""Test scenarios for processor handling merge conflicts.

This scenario tests how the processor handles conflicts:
1. Rebase conflicts during initial rebase (409 from GitLab)
2. Conflicts discovered after rebase starts (polling finds has_conflicts=True)
3. Conflict for one MR doesn't affect other MRs in the queue
"""

from __future__ import annotations

from vedro import given, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabConflictError
from gitlab_queue.core.processor import ProcessingResult
from scenarios.unit.processor._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
    instant_poll,
)


@scenario()
async def process_mr_with_immediate_conflict():
    """Test MR processing when rebase immediately returns conflict (409)."""

    with given("a processor whose GitLab client raises GitLabConflictError on rebase"):
        processor = create_mock_processor()
        processor.gitlab_client.rebase_mr_error = GitLabConflictError("Merge conflict")

        sm = create_mock_state_machine()
        ctx = create_processing_context(mr_iid=44, state_machine=sm)

    with when("processor attempts to rebase the MR"):
        result = await processor._process_rebase(ctx)

    with then("result is CONFLICT and rebase_failed was triggered on the state machine"):
        assert result == ProcessingResult.CONFLICT
        assert len(sm.rebase_failed_calls) == 1


@scenario()
async def process_mr_with_conflict_during_rebase():
    """Test MR processing when conflict is discovered during rebase polling."""

    with given("a processor whose GitLab client reports has_conflicts after rebase"):
        processor = create_mock_processor(poll_fn=instant_poll)
        # rebase_status: (rebase_in_progress=False, has_conflicts=True)
        processor.gitlab_client.rebase_status = (False, True)

        sm = create_mock_state_machine()
        ctx = create_processing_context(mr_iid=45, state_machine=sm)

    with when("processor waits for rebase and polls status"):
        result = await processor._wait_for_rebase(ctx)

    with then("result is CONFLICT and rebase_failed was triggered on the state machine"):
        assert result == ProcessingResult.CONFLICT
        assert len(sm.rebase_failed_calls) == 1


@scenario()
async def process_mr_with_conflict_after_multiple_mrs():
    """Test that conflict handling for one MR doesn't affect other MRs in queue."""

    with given("two MRs in queue and the first one has a rebase conflict"):
        processor = create_mock_processor()
        processor.gitlab_client.rebase_mr_error = GitLabConflictError("Merge conflict")

        item_46 = create_test_queue_item(mr_iid=46, state="queued")
        item_47 = create_test_queue_item(mr_iid=47, state="queued")
        processor.queue_manager.add_item(item_46)
        processor.queue_manager.add_item(item_47)

        sm = create_mock_state_machine()
        ctx = create_processing_context(mr_iid=46, state_machine=sm)

    with when("processor attempts to rebase MR 46"):
        result = await processor._process_rebase(ctx)

    with then("MR 46 fails with CONFLICT but MR 47 remains queued"):
        assert result == ProcessingResult.CONFLICT

        second_item = await processor.queue_manager.get_queue_item(99999, 47)
        assert second_item is not None
        assert second_item.state == "queued"


__all__ = [
    "process_mr_with_conflict_after_multiple_mrs",
    "process_mr_with_conflict_during_rebase",
    "process_mr_with_immediate_conflict",
]
