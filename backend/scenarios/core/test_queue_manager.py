"""Unit tests for QueueManager."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.core.queue import (
    QueueError,
    QueueItemNotFoundError,
    QueueManager,
)
from gitlab_queue.models.mr import Author, MergeRequest
from gitlab_queue.models.queue_item import QueueItem


def create_mock_database():
    """Create a mock database with async context managers."""
    db = MagicMock()

    # Create async context managers for session and transaction
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock()
    session_cm.__aexit__ = AsyncMock(return_value=None)

    transaction_cm = AsyncMock()
    transaction_cm.__aenter__ = AsyncMock()
    transaction_cm.__aexit__ = AsyncMock(return_value=None)

    db.session.return_value = session_cm
    db.transaction.return_value = transaction_cm

    return db, session_cm, transaction_cm


def create_test_mr(iid: int = 123, title: str = "Test MR") -> MergeRequest:
    """Create a test MergeRequest."""
    return MergeRequest(
        iid=iid,
        title=title,
        state="opened",
        labels=["feature"],
        sha="abc123",
        source_branch="feature",
        target_branch="master",
        merge_status="can_be_merged",
        author=Author(id=1, name="Test User", username="testuser"),
    )


def create_mock_row(
    iid: int = 123,
    status: str = "queued",
    is_hotfix: int = 0,
) -> dict:
    """Create a mock database row."""
    return {
        "iid": iid,
        "title": "Test MR",
        "author_name": "Test User",
        "author_username": "testuser",
        "author_avatar": None,
        "status": status,
        "is_hotfix": is_hotfix,
        "labels": "[]",
        "target_branch": "master",
        "queued_at": datetime.now(UTC).isoformat(),
        "started_at": None,
        "finished_at": None,
        "pipeline_id": None,
        "pipeline_status": None,
        "retry_count": 0,
        "last_error": None,
    }


class Scenario(vedro.Scenario):
    subject = "create queue manager"

    def given_mock_database(self):
        self.db, _, _ = create_mock_database()

    def when_queue_manager_is_created(self):
        self.queue_manager = QueueManager(db=self.db)

    def then_it_should_have_database_reference(self):
        assert self.queue_manager.db is self.db


class Scenario__queue_item_not_found_error(vedro.Scenario):
    subject = "QueueItemNotFoundError contains MR IID"

    def given_mr_iid(self):
        self.mr_iid = 456

    def when_error_is_created(self):
        self.error = QueueItemNotFoundError(self.mr_iid)

    def then_it_should_contain_mr_iid(self):
        assert self.error.mr_iid == self.mr_iid
        assert "456" in str(self.error)
        assert "not found" in str(self.error).lower()


class Scenario__queue_error_is_base_exception(vedro.Scenario):
    subject = "QueueError is base exception for queue operations"

    def when_checking_inheritance(self):
        self.is_base_class = issubclass(QueueItemNotFoundError, QueueError)

    def then_it_should_be_subclass(self):
        assert self.is_base_class is True


class Scenario__row_to_queue_item_conversion(vedro.Scenario):
    subject = "convert database row to QueueItem"

    def given_queue_manager_and_row(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)
        self.row = create_mock_row(iid=789, status="testing", is_hotfix=1)

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_it_should_create_queue_item(self):
        assert isinstance(self.item, QueueItem)
        assert self.item.mr_iid == 789
        assert self.item.state == "testing"
        assert self.item.is_hotfix is True

    def and_it_should_parse_datetime(self):
        assert self.item.queued_at is not None
        assert isinstance(self.item.queued_at, datetime)


class Scenario__row_to_queue_item_with_labels(vedro.Scenario):
    subject = "convert row with JSON labels to QueueItem"

    def given_row_with_labels(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)
        self.row = create_mock_row()
        self.row["labels"] = '["feature", "urgent", "merge_queue"]'

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_it_should_parse_labels(self):
        assert self.item.labels == ["feature", "urgent", "merge_queue"]


class Scenario__row_to_queue_item_with_timestamps(vedro.Scenario):
    subject = "convert row with timestamps to QueueItem"

    def given_row_with_timestamps(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)
        self.now = datetime.now(UTC)
        self.row = create_mock_row()
        self.row["started_at"] = self.now.isoformat()
        self.row["finished_at"] = self.now.isoformat()

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_it_should_parse_timestamps(self):
        assert self.item.started_at is not None
        assert self.item.finished_at is not None
        assert isinstance(self.item.started_at, datetime)
        assert isinstance(self.item.finished_at, datetime)


class Scenario__row_to_queue_item_with_pipeline_info(vedro.Scenario):
    subject = "convert row with pipeline info to QueueItem"

    def given_row_with_pipeline(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)
        self.row = create_mock_row()
        self.row["pipeline_id"] = 12345
        self.row["pipeline_status"] = "running"
        self.row["retry_count"] = 2
        self.row["last_error"] = "Previous pipeline failed"

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_it_should_include_pipeline_info(self):
        assert self.item.pipeline_id == 12345
        assert self.item.pipeline_status == "running"
        assert self.item.retry_count == 2
        assert self.item.last_error == "Previous pipeline failed"


class Scenario__row_to_queue_item_empty_labels(vedro.Scenario):
    subject = "convert row with empty labels"

    def given_row_with_empty_labels(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)
        self.row = create_mock_row()
        self.row["labels"] = ""

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_labels_should_be_empty_list(self):
        assert self.item.labels == []


class Scenario__row_to_queue_item_none_labels(vedro.Scenario):
    subject = "convert row with None labels"

    def given_row_with_none_labels(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)
        self.row = create_mock_row()
        self.row["labels"] = None

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_labels_should_be_empty_list(self):
        assert self.item.labels == []


class Scenario__row_with_datetime_objects(vedro.Scenario):
    subject = "convert row with datetime objects (not strings)"

    def given_row_with_datetime_objects(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)
        self.now = datetime.now(UTC)
        self.row = create_mock_row()
        self.row["queued_at"] = self.now  # datetime object, not string
        self.row["started_at"] = self.now
        self.row["finished_at"] = self.now

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_it_should_handle_datetime_objects(self):
        assert self.item.queued_at == self.now
        assert self.item.started_at == self.now
        assert self.item.finished_at == self.now


class Scenario__row_to_queue_item_invalid_json_labels(vedro.Scenario):
    subject = "convert row with invalid JSON labels gracefully"

    def given_row_with_invalid_json_labels(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)
        self.row = create_mock_row(iid=999)
        self.row["labels"] = "not valid json {"

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_labels_should_be_empty_list(self):
        assert self.item.labels == []

    def and_item_should_be_valid(self):
        assert self.item.mr_iid == 999
