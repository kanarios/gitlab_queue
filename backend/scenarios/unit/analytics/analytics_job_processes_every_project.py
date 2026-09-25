"""Analytics jobs run with a project-scoped unit of work per configured project."""

from __future__ import annotations

from types import SimpleNamespace

import vedro

from gitlab_queue.jobs.analytics import AnalyticsJobProcessor
from scenarios.fakes import FakeUnitOfWork


class Scenario(vedro.Scenario):
    subject = "hourly analytics job collects a separate snapshot for every configured project"

    def given_processor_with_two_project_contexts(self):
        self.project_ids = [101, 202]
        self.uows = {project_id: FakeUnitOfWork() for project_id in self.project_ids}
        self.created_project_ids: list[int] = []

        def create_uow(_database, *, auto_commit: bool, project_id: int):
            assert auto_commit is True
            self.created_project_ids.append(project_id)
            return self.uows[project_id]

        settings = SimpleNamespace(projects=[SimpleNamespace(project_id=project_id) for project_id in self.project_ids])
        self.processor = AnalyticsJobProcessor(
            database=object(),
            settings=settings,
            uow_factory=create_uow,
        )

    async def when_hourly_snapshot_job_runs(self):
        await self.processor._save_hourly_snapshot()

    def then_it_creates_a_scoped_unit_of_work_for_each_project(self):
        assert self.created_project_ids == self.project_ids

    def and_it_collects_queue_and_history_data_for_each_project(self):
        for project_id in self.project_ids:
            uow = self.uows[project_id]
            assert len(uow.merge_requests.count_active_calls) == 1
            assert len(uow.history.get_stats_calls) == 1
            assert len(uow.analytics.save_hourly_snapshot_calls) == 1
