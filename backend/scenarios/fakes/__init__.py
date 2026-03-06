from .call_recorder import CallArgs, CallRecorder
from .database import FakeDatabase, FakeResult, FakeSession
from .gitlab_client import FakeGitLabClient
from .handler import FakeHandler, FakeHandlerFactory
from .models import (
    create_author,
    create_job,
    create_mr,
    create_note,
    create_pipeline,
)
from .notifier import FakeNotifier
from .position_notifier import FakePositionNotifier
from .queue_manager import FakeQueueManager
from .rebase_handler import FakeRebaseDuringTestingHandler
from .retry_call_state import FakeNextAction, FakeOutcome, FakeRetryCallState
from .retry_manager import FakeRetryManager
from .settings import FakeSettings
from .state_machine import FakeCurrentState, FakeStateMachine, FakeStateMachineFactory
from .unit_of_work import (
    AnalyticsMetrics,
    DailyAggregationResult,
    FakeAnalyticsRepo,
    FakeHistoryRepo,
    FakeMergeRequestsRepo,
    FakeUnitOfWork,
    HistoryItemModel,
    HistoryStatsResult,
    HourlyStats,
    PaginatedHistoryResult,
)
from .websocket import FakeWebSocket, FakeWebSocketManager

__all__ = [
    "AnalyticsMetrics",
    "CallArgs",
    "CallRecorder",
    "DailyAggregationResult",
    "FakeAnalyticsRepo",
    "FakeCurrentState",
    "FakeDatabase",
    "FakeGitLabClient",
    "FakeHandler",
    "FakeHandlerFactory",
    "FakeHistoryRepo",
    "FakeMergeRequestsRepo",
    "FakeNextAction",
    "FakeNotifier",
    "FakeOutcome",
    "FakePositionNotifier",
    "FakeQueueManager",
    "FakeRebaseDuringTestingHandler",
    "FakeResult",
    "FakeRetryCallState",
    "FakeRetryManager",
    "FakeSession",
    "FakeSettings",
    "FakeStateMachine",
    "FakeStateMachineFactory",
    "FakeUnitOfWork",
    "FakeWebSocket",
    "FakeWebSocketManager",
    "HistoryItemModel",
    "HistoryStatsResult",
    "HourlyStats",
    "PaginatedHistoryResult",
    "create_author",
    "create_job",
    "create_mr",
    "create_note",
    "create_pipeline",
]
