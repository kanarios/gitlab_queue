"""Test calculate duration for None item."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "calculate duration for none item"

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
