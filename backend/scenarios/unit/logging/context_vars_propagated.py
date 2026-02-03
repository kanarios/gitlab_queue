"""Test that context variables (request_id) propagate to log entries."""

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
        self.request_id = "test-req-123"

    def when_log_context_is_entered(self):
        with LogContext(request_id=self.request_id):
            self.value_inside = request_id_ctx.get()
        self.value_outside = request_id_ctx.get()

    def then_request_id_should_be_set_inside_context(self):
        assert self.value_inside == self.request_id, (
            f"Expected '{self.request_id}' inside context, got '{self.value_inside}'"
        )

    def and_request_id_should_be_reset_outside_context(self):
        assert self.value_outside is None, f"Expected None outside context, got '{self.value_outside}'"


class Scenario2(vedro.Scenario):
    subject = "mr_iid context variable propagates within LogContext"

    def given_log_context_with_mr_iid(self):
        self.mr_iid = 42

    def when_log_context_is_entered(self):
        with LogContext(mr_iid=self.mr_iid):
            self.value_inside = mr_iid_ctx.get()
        self.value_outside = mr_iid_ctx.get()

    def then_mr_iid_should_be_set_inside_context(self):
        assert self.value_inside == self.mr_iid, f"Expected {self.mr_iid} inside context, got {self.value_inside}"

    def and_mr_iid_should_be_reset_outside_context(self):
        assert self.value_outside is None, f"Expected None outside context, got {self.value_outside}"


class Scenario3(vedro.Scenario):
    subject = "operation context variable propagates within LogContext"

    def given_log_context_with_operation(self):
        self.operation = "rebase"

    def when_log_context_is_entered(self):
        with LogContext(operation=self.operation):
            self.value_inside = operation_ctx.get()
        self.value_outside = operation_ctx.get()

    def then_operation_should_be_set_inside_context(self):
        assert self.value_inside == self.operation, (
            f"Expected '{self.operation}' inside context, got '{self.value_inside}'"
        )

    def and_operation_should_be_reset_outside_context(self):
        assert self.value_outside is None, f"Expected None outside context, got {self.value_outside}"


class Scenario4(vedro.Scenario):
    subject = "multiple context variables propagate together"

    def given_log_context_with_all_fields(self):
        self.request_id = "req-multi-456"
        self.mr_iid = 99
        self.operation = "merge"

    def when_log_context_is_entered_with_all_fields(self):
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
        assert self.req_inside == self.request_id
        assert self.iid_inside == self.mr_iid
        assert self.op_inside == self.operation

    def and_all_values_should_be_reset_outside_context(self):
        assert self.req_outside is None
        assert self.iid_outside is None
        assert self.op_outside is None
