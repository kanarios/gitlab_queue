"""Test that context variables (request_id, mr_iid, operation) propagate within LogContext.

Covers LogContext propagation for all three context variables:
- request_id_ctx: tracks the current request ID
- mr_iid_ctx: tracks the current merge request IID
- operation_ctx: tracks the current operation name
"""

from __future__ import annotations

import vedro

from gitlab_queue.utils.logging import (
    LogContext,
    mr_iid_ctx,
    operation_ctx,
    request_id_ctx,
)


class Scenario(vedro.Scenario):
    subject = "request_id context variable propagates within LogContext"

    def given_log_context_with_request_id(self):
        """
        Sets a fixed request_id for the scenario.

        Assigns the string "test-req-123" to self.request_id for use in subsequent steps.
        """
        self.request_id = "test-req-123"

    def when_log_context_is_entered(self):
        """
        Enter a LogContext with the scenario's request_id and capture the request_id value both inside the context and after exiting it.

        This sets:
        - self.value_inside: the value of request_id_ctx.get() while inside the LogContext.
        - self.value_outside: the value of request_id_ctx.get() after the LogContext has been exited.
        """
        with LogContext(request_id=self.request_id):
            self.value_inside = request_id_ctx.get()
        self.value_outside = request_id_ctx.get()

    def then_request_id_should_be_set_inside_context(self):
        assert self.value_inside == self.request_id

    def and_request_id_should_be_reset_outside_context(self):
        """
        Assert that the request_id context variable is unset outside the LogContext.

        Raises:
            AssertionError: If the stored outside value is not `None`.
        """
        assert self.value_outside is None


class Scenario2(vedro.Scenario):
    subject = "mr_iid context variable propagates within LogContext"

    def given_log_context_with_mr_iid(self):
        """
        Set the scenario's `mr_iid` attribute to 42 for use in subsequent steps.
        """
        self.mr_iid = 42

    def when_log_context_is_entered(self):
        """
        Enter a LogContext with mr_iid set and record the mr_iid_ctx value inside and after exiting the context.

        Sets self.value_inside to the context value observed while inside the LogContext and self.value_outside to the value observed after the context is exited.
        """
        with LogContext(mr_iid=self.mr_iid):
            self.value_inside = mr_iid_ctx.get()
        self.value_outside = mr_iid_ctx.get()

    def then_mr_iid_should_be_set_inside_context(self):
        """
        Assert that the mr_iid context variable equals the expected merge request IID inside the LogContext.
        """
        assert self.value_inside == self.mr_iid

    def and_mr_iid_should_be_reset_outside_context(self):
        """
        Asserts that the mr_iid context variable is reset to None outside of the LogContext.

        Checks that the captured outside value (self.value_outside) is None, indicating the context was cleared after exiting the LogContext.
        """
        assert self.value_outside is None


class Scenario3(vedro.Scenario):
    subject = "operation context variable propagates within LogContext"

    def given_log_context_with_operation(self):
        """
        Prepare the scenario by setting the operation value used in the test.

        Sets self.operation to "rebase" so subsequent steps can verify LogContext propagation.
        """
        self.operation = "rebase"

    def when_log_context_is_entered(self):
        """
        Enters a LogContext with the scenario's operation and records the operation context value inside and after exiting the context.

        Sets self.value_inside to the value of operation_ctx.get() from within the LogContext and sets self.value_outside to the value of operation_ctx.get() after the context has been exited.
        """
        with LogContext(operation=self.operation):
            self.value_inside = operation_ctx.get()
        self.value_outside = operation_ctx.get()

    def then_operation_should_be_set_inside_context(self):
        """
        Asserts that the captured operation context value matches the expected operation inside the LogContext.

        Raises:
            AssertionError: If the captured context value does not equal self.operation.
        """
        assert self.value_inside == self.operation

    def and_operation_should_be_reset_outside_context(self):
        """
        Asserts that the operation context variable is reset to None after exiting LogContext.

        Raises:
            AssertionError: If the operation context is not None.
        """
        assert self.value_outside is None


class Scenario4(vedro.Scenario):
    subject = "multiple context variables propagate together"

    def given_log_context_with_all_fields(self):
        self.request_id = "req-multi-456"
        self.mr_iid = 99
        self.operation = "merge"

    def when_log_context_is_entered_with_all_fields(self):
        """
        Enter a LogContext with request_id, mr_iid, and operation set and capture each context variable's value inside and after exiting.

        Sets req_inside, iid_inside, and op_inside to the values observed while inside the context, and sets req_outside, iid_outside, and op_outside to the values observed after exiting the context.
        """
        with LogContext(
            request_id=self.request_id,
            mr_iid=self.mr_iid,
            operation=self.operation,
        ):
            self.req_inside = request_id_ctx.get()
            self.iid_inside = mr_iid_ctx.get()
            self.op_inside = operation_ctx.get()
        self.req_outside = request_id_ctx.get()
        self.iid_outside = mr_iid_ctx.get()
        self.op_outside = operation_ctx.get()

    def then_all_values_should_be_set_inside_context(self):
        """
        Asserts that the request_id, mr_iid, and operation captured inside the LogContext match the expected values.

        Raises:
            AssertionError: If any captured value does not equal its expected value.
        """
        assert self.req_inside == self.request_id
        assert self.iid_inside == self.mr_iid
        assert self.op_inside == self.operation

    def and_all_values_should_be_reset_outside_context(self):
        """
        Asserts that the captured request_id, mr_iid, and operation values are None outside the LogContext.

        Raises:
                AssertionError: If any of `req_outside`, `iid_outside`, or `op_outside` is not None.
        """
        assert self.req_outside is None
        assert self.iid_outside is None
        assert self.op_outside is None
