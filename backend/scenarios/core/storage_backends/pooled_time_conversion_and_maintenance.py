import asyncio
from datetime import UTC, datetime, timedelta

from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.integration.repositories._helpers import create_test_hourly_model
from sqlalchemy import event, text
from vedro import given, scenario, then, when

from gitlab_queue.db.time_sql import epoch_sql
from gitlab_queue.jobs.analytics import AnalyticsJobProcessor

from ._helpers import migrated_storage


async def non_utc_server_default(database):
    if database.engine.dialect.name == "postgresql":
        name = database.engine.url.database
        assert name.startswith("gq_test_")
        async with database.engine.connect() as connection:
            connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
            await connection.execute(text(f"ALTER DATABASE \"{name}\" SET timezone TO 'Pacific/Honolulu'"))


async def held_conversion(database, barrier, instant):
    async with database.engine.connect() as connection:
        value = (
            await connection.execute(
                text(f"SELECT {epoch_sql('CAST(:instant AS TEXT)', connection.dialect.name)}"), {"instant": instant}
            )
        ).scalar_one()
        await barrier.wait()
        return float(value)


@scenario()
async def every_pooled_connection_interprets_naive_timestamps_as_utc():
    async with migrated_storage() as database:
        with given("a non-UTC PostgreSQL server default and more concurrent connections than the base pool"):
            await non_utc_server_default(database)
            barrier = asyncio.Barrier(4)
            naive = "2026-10-17 12:00:00.123456"

        with when("four physical connections parse the same microsecond timestamp"):
            converted = await asyncio.gather(*(held_conversion(database, barrier, naive) for _ in range(4)))

        with then("every connection uses the same UTC instant"):
            assert converted == [datetime(2026, 10, 17, 12, 0, 0, 123456, tzinfo=UTC).timestamp()] * 4


@scenario()
async def scheduled_analytics_cleanup_vacuums_outside_transactions():
    async with migrated_storage() as database:
        with given("expired hourly analytics for the configured project and an independent foreign project"):
            old = (datetime.now(UTC) - timedelta(days=60)).isoformat()
            first = create_test_hourly_model(timestamp=old)
            first.project_id = 123
            foreign = create_test_hourly_model(timestamp=old)
            foreign.project_id = 456
            async with database.transaction() as session:
                session.add_all([first, foreign])
            successful = []

            def observed(_connection, _cursor, statement, _params, _context, _many):
                successful.append(statement)

            event.listen(database.engine.sync_engine, "after_cursor_execute", observed)
            processor = AnalyticsJobProcessor(database, created_test_settings())

        with when("the production hourly retention callback runs with its actual VACUUM operation"):
            await processor._cleanup_hourly_analytics()
            async with database.session() as session:
                remaining = (await session.execute(text("SELECT project_id FROM analytics_hourly"))).scalars().all()
                await session.commit()

        with then("cleanup preserves foreign records and VACUUM succeeds without a transaction"):
            assert remaining == [456]
            assert successful.count("VACUUM") == 1
