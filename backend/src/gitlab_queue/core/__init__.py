"""Core module for GitLab Merge Queue Bot.

Contains the main business logic components:
- Queue management
- MR processing
- State machine
- Notifier
- Processor
"""

from gitlab_queue.core.notifier import COMMENT_TEMPLATES, MRNotifier
from gitlab_queue.core.processor import (
    MergeProcessor,
    ProcessingContext,
    ProcessingResult,
    create_processor,
)
from gitlab_queue.core.queue import QueueError, QueueItemNotFoundError, QueueManager
from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier
from gitlab_queue.core.state_machine import MRStateMachine, create_state_machine_for_mr

__all__: list[str] = [
    "COMMENT_TEMPLATES",
    "MRNotifier",
    "MRStateMachine",
    "MergeProcessor",
    "ProcessingContext",
    "ProcessingResult",
    "QueueError",
    "QueueItemNotFoundError",
    "QueueManager",
    "QueuePositionNotifier",
    "create_processor",
    "create_state_machine_for_mr",
]
