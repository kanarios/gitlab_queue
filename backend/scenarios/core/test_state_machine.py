"""Unit tests for MRStateMachine."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import vedro
from statemachine.exceptions import TransitionNotAllowed

from gitlab_queue.core.state_machine import MRStateMachine, create_state_machine_for_mr
from gitlab_queue.models.queue_item import QueueItem


def create_mock_notifier():
    """Create a mock MRNotifier."""
    notifier = MagicMock()
    notifier.notify = AsyncMock()
    notifier.remove_queue_label = AsyncMock()
    notifier.build_pipeline_url = MagicMock(return_value="https://gitlab.com/pipeline/123")
    return notifier


def create_mock_queue_manager():
    """Create a mock QueueManager."""
    qm = MagicMock()
    qm.get_queue_position = AsyncMock(return_value=1)
    qm.get_queue_length = AsyncMock(return_value=5)
    qm.update_mr_state = AsyncMock(return_value=True)
    qm.complete_mr = AsyncMock()
    qm.get_queue_item = AsyncMock(
        return_value=QueueItem(
            mr_iid=123,
            title="Test MR",
            author_name="Test",
            author_username="test",
            target_branch="master",
            state="queued",
            queued_at=datetime.now(UTC),
        )
    )
    return qm


async def create_state_machine(
    notifier,
    queue_manager,
    mr_iid: int = 123,
    *,
    start_value: str | None = None,
    target_branch: str = "master",
) -> MRStateMachine:
    """Create and activate a state machine for testing."""
    sm = MRStateMachine(
        notifier=notifier,
        queue_manager=queue_manager,
        mr_iid=mr_iid,
        start_value=start_value,
        target_branch=target_branch,
    )
    await sm.activate_initial_state()
    return sm


class Scenario(vedro.Scenario):
    subject = "create state machine with initial queued state"

    def given_dependencies(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()

    async def when_state_machine_is_created(self):
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
        )

    def then_it_should_start_in_queued_state(self):
        assert self.sm.current_state.id == "queued"


class Scenario__create_with_custom_start_state(vedro.Scenario):
    subject = "create state machine with custom start state"

    def given_dependencies(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()

    async def when_state_machine_is_created_with_start_value(self):
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            start_value="testing",
        )

    def then_it_should_start_in_specified_state(self):
        assert self.sm.current_state.id == "testing"


class Scenario__create_with_target_branch(vedro.Scenario):
    subject = "create state machine with custom target branch"

    def given_dependencies(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()

    async def when_state_machine_is_created_with_target_branch(self):
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            target_branch="main",
        )

    def then_it_should_have_correct_target_branch(self):
        assert self.sm.target_branch == "main"


class Scenario__valid_transitions_from_queued(vedro.Scenario):
    subject = "queued state can transition to rebasing"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
        )

    async def when_start_processing_is_triggered(self):
        await self.sm.trigger_start_processing()

    def then_it_should_be_in_rebasing_state(self):
        assert self.sm.current_state.id == "rebasing"


class Scenario__valid_transitions_from_rebasing_to_testing(vedro.Scenario):
    subject = "rebasing state can transition to testing"

    async def given_state_machine_in_rebasing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            start_value="rebasing",
        )

    async def when_rebase_complete_is_triggered(self):
        await self.sm.trigger_rebase_complete(
            pipeline_id=456,
            pipeline_url="https://gitlab.com/pipeline/456",
        )

    def then_it_should_be_in_testing_state(self):
        assert self.sm.current_state.id == "testing"


class Scenario__valid_transitions_from_rebasing_to_failed(vedro.Scenario):
    subject = "rebasing state can transition to failed"

    async def given_state_machine_in_rebasing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            start_value="rebasing",
        )

    async def when_rebase_failed_is_triggered(self):
        await self.sm.trigger_rebase_failed(
            conflicted_files=["file1.py", "file2.py"],
            error_message="Merge conflict",
        )

    def then_it_should_be_in_failed_state(self):
        assert self.sm.current_state.id == "failed"


class Scenario__valid_transitions_from_testing_to_merging(vedro.Scenario):
    subject = "testing state can transition to merging"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            start_value="testing",
        )

    async def when_pipeline_success_is_triggered(self):
        await self.sm.trigger_pipeline_success()

    def then_it_should_be_in_merging_state(self):
        assert self.sm.current_state.id == "merging"


class Scenario__valid_transitions_from_testing_to_failed(vedro.Scenario):
    subject = "testing state can transition to failed"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            start_value="testing",
        )

    async def when_pipeline_failed_is_triggered(self):
        await self.sm.trigger_pipeline_failed(
            failed_jobs=["test", "lint"],
            retry_count=2,
            error_message="Tests failed",
        )

    def then_it_should_be_in_failed_state(self):
        assert self.sm.current_state.id == "failed"


class Scenario__valid_transitions_from_merging_to_merged(vedro.Scenario):
    subject = "merging state can transition to merged"

    async def given_state_machine_in_merging(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            start_value="merging",
        )

    async def when_merge_success_is_triggered(self):
        await self.sm.trigger_merge_success()

    def then_it_should_be_in_merged_state(self):
        assert self.sm.current_state.id == "merged"


class Scenario__valid_transitions_from_merging_to_failed(vedro.Scenario):
    subject = "merging state can transition to failed"

    async def given_state_machine_in_merging(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            start_value="merging",
        )

    async def when_merge_failed_is_triggered(self):
        await self.sm.trigger_merge_failed(error_message="Merge conflict")

    def then_it_should_be_in_failed_state(self):
        assert self.sm.current_state.id == "failed"


class Scenario__mark_removed_from_queued(vedro.Scenario):
    subject = "queued state can transition to removed"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
        )

    async def when_mark_removed_is_triggered(self):
        await self.sm.trigger_mark_removed(reason="label_removed")

    def then_it_should_be_in_removed_state(self):
        assert self.sm.current_state.id == "removed"


class Scenario__mark_removed_from_testing(vedro.Scenario):
    subject = "testing state can transition to removed"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            start_value="testing",
        )

    async def when_mark_removed_is_triggered(self):
        await self.sm.trigger_mark_removed(reason="closed")

    def then_it_should_be_in_removed_state(self):
        assert self.sm.current_state.id == "removed"


class Scenario__calculate_duration_seconds(vedro.Scenario):
    subject = "calculate duration for short time"

    async def given_state_machine(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
        )

    def when_calculating_duration_for_recent_item(self):
        now = datetime.now(UTC)
        item = QueueItem(
            mr_iid=123,
            title="Test",
            author_name="Test",
            author_username="test",
            target_branch="master",
            state="queued",
            queued_at=now,
        )
        self.duration = self.sm._calculate_duration(item)

    def then_it_should_return_seconds_format(self):
        assert "s" in self.duration


class Scenario__calculate_duration_none_item(vedro.Scenario):
    subject = "calculate duration for None item"

    async def given_state_machine(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
        )

    def when_calculating_duration_for_none(self):
        self.duration = self.sm._calculate_duration(None)

    def then_it_should_return_unknown(self):
        assert self.duration == "unknown"


class Scenario__timeout_transition(vedro.Scenario):
    subject = "trigger timeout transitions to failed"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            start_value="testing",
        )

    async def when_timeout_is_triggered(self):
        await self.sm.trigger_timeout(max_wait_hours=2)

    def then_it_should_be_in_failed_state(self):
        assert self.sm.current_state.id == "failed"


class Scenario__final_states_are_terminal(vedro.Scenario):
    subject = "merged, failed, and removed are final states"

    def given_state_machine_class(self):
        pass

    def when_checking_final_states(self):
        self.merged_is_final = MRStateMachine.merged.final
        self.failed_is_final = MRStateMachine.failed.final
        self.removed_is_final = MRStateMachine.removed.final

    def then_all_should_be_final(self):
        assert self.merged_is_final is True
        assert self.failed_is_final is True
        assert self.removed_is_final is True


class Scenario__queued_is_initial_state(vedro.Scenario):
    subject = "queued is the initial state"

    def when_checking_initial_state(self):
        self.is_initial = MRStateMachine.queued.initial

    def then_queued_should_be_initial(self):
        assert self.is_initial is True


# =============================================================================
# Invalid Transition Tests
# =============================================================================


class Scenario__invalid_transition_from_merged(vedro.Scenario):
    subject = "merged state cannot transition to other states"

    async def given_state_machine_in_merged(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="merged",
        )

    async def when_start_processing_is_triggered(self):
        self.exception = None
        try:
            await self.sm.trigger_start_processing()
        except TransitionNotAllowed as e:
            self.exception = e

    def then_it_should_raise_transition_not_allowed(self):
        assert self.exception is not None
        assert isinstance(self.exception, TransitionNotAllowed)


class Scenario__invalid_transition_from_failed(vedro.Scenario):
    subject = "failed state cannot transition to other states"

    async def given_state_machine_in_failed(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="failed",
        )

    async def when_start_processing_is_triggered(self):
        self.exception = None
        try:
            await self.sm.trigger_start_processing()
        except TransitionNotAllowed as e:
            self.exception = e

    def then_it_should_raise_transition_not_allowed(self):
        assert self.exception is not None
        assert isinstance(self.exception, TransitionNotAllowed)


class Scenario__invalid_transition_from_removed(vedro.Scenario):
    subject = "removed state cannot transition to other states"

    async def given_state_machine_in_removed(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="removed",
        )

    async def when_start_processing_is_triggered(self):
        self.exception = None
        try:
            await self.sm.trigger_start_processing()
        except TransitionNotAllowed as e:
            self.exception = e

    def then_it_should_raise_transition_not_allowed(self):
        assert self.exception is not None
        assert isinstance(self.exception, TransitionNotAllowed)


class Scenario__invalid_transition_queued_to_testing(vedro.Scenario):
    subject = "queued state cannot directly transition to testing"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
        )

    async def when_rebase_complete_is_triggered(self):
        self.exception = None
        try:
            await self.sm.trigger_rebase_complete(
                pipeline_id=456,
                pipeline_url="https://gitlab.com/pipeline/456",
            )
        except TransitionNotAllowed as e:
            self.exception = e

    def then_it_should_raise_transition_not_allowed(self):
        assert self.exception is not None
        assert isinstance(self.exception, TransitionNotAllowed)


class Scenario__invalid_transition_queued_to_merging(vedro.Scenario):
    subject = "queued state cannot directly transition to merging"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
        )

    async def when_pipeline_success_is_triggered(self):
        self.exception = None
        try:
            await self.sm.trigger_pipeline_success()
        except TransitionNotAllowed as e:
            self.exception = e

    def then_it_should_raise_transition_not_allowed(self):
        assert self.exception is not None
        assert isinstance(self.exception, TransitionNotAllowed)


class Scenario__invalid_transition_testing_to_rebasing(vedro.Scenario):
    subject = "testing state cannot transition back to rebasing"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="testing",
        )

    async def when_start_processing_is_triggered(self):
        self.exception = None
        try:
            await self.sm.trigger_start_processing()
        except TransitionNotAllowed as e:
            self.exception = e

    def then_it_should_raise_transition_not_allowed(self):
        assert self.exception is not None
        assert isinstance(self.exception, TransitionNotAllowed)


# =============================================================================
# Callback Verification Tests
# =============================================================================


class Scenario__on_enter_rebasing_calls_notifier(vedro.Scenario):
    subject = "on_enter_rebasing calls notifier with correct template"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            target_branch="main",
        )

    async def when_start_processing_is_triggered(self):
        await self.sm.trigger_start_processing()

    def then_notifier_should_be_called_with_rebasing_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "rebasing"  # template

    def and_notify_should_include_target_branch(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("target_branch") == "main"


class Scenario__on_enter_testing_calls_notifier(vedro.Scenario):
    subject = "on_enter_testing calls notifier with pipeline info"

    async def given_state_machine_in_rebasing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="rebasing",
        )

    async def when_rebase_complete_is_triggered(self):
        await self.sm.trigger_rebase_complete(
            pipeline_id=456,
            pipeline_url="https://gitlab.com/pipeline/456",
        )

    def then_notifier_should_be_called_with_testing_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "testing"  # template

    def and_notify_should_include_pipeline_info(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("pipeline_id") == 456
        assert call_kwargs.get("pipeline_url") == "https://gitlab.com/pipeline/456"


class Scenario__on_enter_merging_calls_notifier(vedro.Scenario):
    subject = "on_enter_merging calls notifier with merging template"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="testing",
            target_branch="develop",
        )

    async def when_pipeline_success_is_triggered(self):
        await self.sm.trigger_pipeline_success()

    def then_notifier_should_be_called_with_merging_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "merging"  # template

    def and_notify_should_include_target_branch(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("target_branch") == "develop"


class Scenario__on_enter_merged_calls_notifier(vedro.Scenario):
    subject = "on_enter_merged calls notifier with merged template"

    async def given_state_machine_in_merging(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="merging",
            target_branch="master",
        )

    async def when_merge_success_is_triggered(self):
        await self.sm.trigger_merge_success()

    def then_notifier_should_be_called_with_merged_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "merged"  # template

    def and_notify_should_include_duration_and_target_branch(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert "duration" in call_kwargs
        assert call_kwargs.get("target_branch") == "master"


class Scenario__on_enter_failed_conflict_calls_notifier(vedro.Scenario):
    subject = "on_enter_failed calls notifier with conflict template"

    async def given_state_machine_in_rebasing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="rebasing",
        )

    async def when_rebase_failed_is_triggered(self):
        await self.sm.trigger_rebase_failed(
            conflicted_files=["src/main.py", "tests/test_main.py"],
            error_message="Merge conflict",
        )

    def then_notifier_should_be_called_with_conflict_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "conflict"  # template

    def and_notify_should_include_conflicted_files(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("conflicted_files") == ["src/main.py", "tests/test_main.py"]


class Scenario__on_enter_failed_pipeline_calls_notifier(vedro.Scenario):
    subject = "on_enter_failed calls notifier with pipeline_failed template"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="testing",
        )

    async def when_pipeline_failed_is_triggered(self):
        await self.sm.trigger_pipeline_failed(
            failed_jobs=["test", "lint", "typecheck"],
            retry_count=2,
            error_message="Tests failed",
        )

    def then_notifier_should_be_called_with_pipeline_failed_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "pipeline_failed"  # template

    def and_notify_should_include_failed_jobs_and_retry_count(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("failed_jobs") == ["test", "lint", "typecheck"]
        assert call_kwargs.get("retry_count") == 2


class Scenario__on_enter_failed_timeout_calls_notifier(vedro.Scenario):
    subject = "on_enter_failed calls notifier with timeout template"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="testing",
        )

    async def when_timeout_is_triggered(self):
        await self.sm.trigger_timeout(max_wait_hours=4)

    def then_notifier_should_be_called_with_timeout_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "timeout"  # template

    def and_notify_should_include_max_wait(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("max_wait") == 4


class Scenario__on_enter_removed_label_calls_notifier(vedro.Scenario):
    subject = "on_enter_removed calls notifier with removed_label template"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
        )

    async def when_mark_removed_is_triggered_with_label_removed(self):
        await self.sm.trigger_mark_removed(reason="label_removed")

    def then_notifier_should_be_called_with_removed_label_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "removed_label"  # template

    def and_notify_should_include_position(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert "position" in call_kwargs


class Scenario__on_enter_removed_closed_calls_notifier(vedro.Scenario):
    subject = "on_enter_removed calls notifier with removed_closed template"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="testing",
        )

    async def when_mark_removed_is_triggered_with_closed(self):
        await self.sm.trigger_mark_removed(reason="closed")

    def then_notifier_should_be_called_with_removed_closed_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "removed_closed"  # template


# =============================================================================
# Mark Removed From All States Tests
# =============================================================================


class Scenario__mark_removed_from_rebasing(vedro.Scenario):
    subject = "rebasing state can transition to removed"

    async def given_state_machine_in_rebasing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="rebasing",
        )

    async def when_mark_removed_is_triggered(self):
        await self.sm.trigger_mark_removed(reason="label_removed")

    def then_it_should_be_in_removed_state(self):
        assert self.sm.current_state.id == "removed"


class Scenario__mark_removed_from_merging(vedro.Scenario):
    subject = "merging state can transition to removed"

    async def given_state_machine_in_merging(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="merging",
        )

    async def when_mark_removed_is_triggered(self):
        await self.sm.trigger_mark_removed(reason="closed")

    def then_it_should_be_in_removed_state(self):
        assert self.sm.current_state.id == "removed"


# =============================================================================
# Non-State-Changing Notification Tests
# =============================================================================


class Scenario__notify_pipeline_retry_stays_in_testing(vedro.Scenario):
    subject = "notify_pipeline_retry stays in testing and calls notifier"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="testing",
        )

    async def when_notify_pipeline_retry_is_called(self):
        await self.sm.notify_pipeline_retry(
            old_pipeline_id=100,
            old_pipeline_url="https://gitlab.com/pipeline/100",
            new_pipeline_id=200,
            new_pipeline_url="https://gitlab.com/pipeline/200",
            retry_count=1,
            max_retries=2,
            failed_jobs=["test"],
        )

    def then_it_should_stay_in_testing_state(self):
        assert self.sm.current_state.id == "testing"

    def and_notifier_should_be_called_with_pipeline_retry_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "pipeline_retry"  # template


class Scenario__notify_position_changed_when_position_differs(vedro.Scenario):
    subject = "notify_position_changed calls notifier when position changed"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        # Return a different position than old_position
        self.queue_manager.get_queue_position = AsyncMock(return_value=2)
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
        )

    async def when_notify_position_changed_is_called_with_old_position_3(self):
        await self.sm.notify_position_changed(old_position=3)

    def then_it_should_stay_in_queued_state(self):
        assert self.sm.current_state.id == "queued"

    def and_notifier_should_be_called_with_position_changed_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "position_changed"  # template

    def and_notify_should_include_old_and_new_position(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("position") == 2
        assert call_kwargs.get("old_position") == 3


class Scenario__notify_position_changed_skips_when_same(vedro.Scenario):
    subject = "notify_position_changed skips notification when position unchanged"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        # Return same position as old_position
        self.queue_manager.get_queue_position = AsyncMock(return_value=2)
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
        )
        # Reset mock after initial state notification
        self.notifier.notify.reset_mock()

    async def when_notify_position_changed_is_called_with_same_position(self):
        await self.sm.notify_position_changed(old_position=2)

    def then_notifier_should_not_be_called(self):
        self.notifier.notify.assert_not_called()


class Scenario__notify_rebase_complete_sends_notification(vedro.Scenario):
    subject = "notify_rebase_complete calls notifier with rebase_complete template"

    async def given_state_machine_in_rebasing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="rebasing",
        )

    async def when_notify_rebase_complete_is_called(self):
        await self.sm.notify_rebase_complete()

    def then_it_should_stay_in_rebasing_state(self):
        assert self.sm.current_state.id == "rebasing"

    def and_notifier_should_be_called_with_rebase_complete_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "rebase_complete"  # template


class Scenario__notify_stale_warning_sends_notification(vedro.Scenario):
    subject = "notify_stale_warning calls notifier with stale_warning template"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
        )

    async def when_notify_stale_warning_is_called(self):
        await self.sm.notify_stale_warning(warning_hours=12)

    def then_it_should_stay_in_queued_state(self):
        assert self.sm.current_state.id == "queued"

    def and_notifier_should_be_called_with_stale_warning_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "stale_warning"  # template

    def and_notify_should_include_warning_hours(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("warning_hours") == 12


# =============================================================================
# Factory Function Tests
# =============================================================================


class Scenario__factory_creates_new_sm_when_no_item(vedro.Scenario):
    subject = "create_state_machine_for_mr creates new SM when no queue item"

    def given_queue_manager_with_no_item(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(return_value=None)

    async def when_factory_is_called(self):
        self.sm = await create_state_machine_for_mr(
            mr_iid=42,
            notifier=self.notifier,
            queue_manager=self.queue_manager,
            target_branch="main",
        )

    def then_it_should_be_in_queued_state(self):
        assert self.sm.current_state.id == "queued"

    def and_it_should_have_correct_target_branch(self):
        assert self.sm.target_branch == "main"


class Scenario__factory_resumes_from_existing_state(vedro.Scenario):
    subject = "create_state_machine_for_mr resumes from existing state"

    def given_queue_manager_with_existing_item_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=QueueItem(
                mr_iid=42,
                title="Existing MR",
                author_name="Test",
                author_username="test",
                target_branch="master",
                state="testing",
                queued_at=datetime.now(UTC),
            )
        )

    async def when_factory_is_called(self):
        self.sm = await create_state_machine_for_mr(
            mr_iid=42,
            notifier=self.notifier,
            queue_manager=self.queue_manager,
        )

    def then_it_should_be_in_testing_state(self):
        assert self.sm.current_state.id == "testing"


# =============================================================================
# Context Passing Tests
# =============================================================================


class Scenario__rebase_complete_passes_pipeline_context(vedro.Scenario):
    subject = "trigger_rebase_complete passes pipeline info to context"

    async def given_state_machine_in_rebasing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="rebasing",
        )

    async def when_rebase_complete_is_triggered(self):
        await self.sm.trigger_rebase_complete(
            pipeline_id=789,
            pipeline_url="https://gitlab.com/pipeline/789",
        )

    def then_context_should_contain_pipeline_info(self):
        assert self.sm._context.get("pipeline_id") == 789
        assert self.sm._context.get("pipeline_url") == "https://gitlab.com/pipeline/789"


class Scenario__rebase_failed_passes_conflict_context(vedro.Scenario):
    subject = "trigger_rebase_failed passes conflict info to context"

    async def given_state_machine_in_rebasing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="rebasing",
        )

    async def when_rebase_failed_is_triggered(self):
        await self.sm.trigger_rebase_failed(
            conflicted_files=["a.py", "b.py"],
            error_message="Conflict in a.py",
        )

    def then_context_should_contain_failure_reason(self):
        assert self.sm._context.get("failure_reason") == "conflict"

    def and_context_should_contain_conflicted_files(self):
        assert self.sm._context.get("conflicted_files") == ["a.py", "b.py"]

    def and_context_should_contain_error_message(self):
        assert self.sm._context.get("error_message") == "Conflict in a.py"


class Scenario__pipeline_failed_passes_jobs_context(vedro.Scenario):
    subject = "trigger_pipeline_failed passes job info to context"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value="testing",
        )

    async def when_pipeline_failed_is_triggered(self):
        await self.sm.trigger_pipeline_failed(
            failed_jobs=["unit_test", "integration_test"],
            retry_count=3,
            error_message="Tests failed",
        )

    def then_context_should_contain_failure_reason(self):
        assert self.sm._context.get("failure_reason") == "pipeline_failed"

    def and_context_should_contain_failed_jobs(self):
        assert self.sm._context.get("failed_jobs") == ["unit_test", "integration_test"]

    def and_context_should_contain_retry_count(self):
        assert self.sm._context.get("retry_count") == 3
