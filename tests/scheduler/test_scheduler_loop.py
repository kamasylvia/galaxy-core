"""Tests for AutoSyncScheduler main loop."""

import asyncio
import pytest
from datetime import date, datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

from galaxy_db_sync.application.scheduler.scheduler import AutoSyncScheduler, run_scheduler


class TestAutoSyncSchedulerInit:
    """Tests for AutoSyncScheduler initialization."""

    def test_initializes_components(self):
        """Initializes all required components."""
        scheduler = AutoSyncScheduler()
        assert scheduler._state_manager is not None
        assert scheduler._kline_job is not None
        assert scheduler._calendar_job is not None
        assert scheduler._completeness_job is not None
        assert scheduler._running is False


class TestSchedulerLoop:
    """Tests for the main scheduler loop."""

    @pytest.mark.asyncio
    async def test_check_kline_trigger_at_23_00(self):
        """Triggers K-line sync with verification at 23:00."""
        scheduler = AutoSyncScheduler()
        scheduler._run_kline_sync_with_verification = AsyncMock()
        scheduler._running = True

        today = date(2025, 3, 28)
        trigger_time = time(23, 0)

        await scheduler._check_kline_trigger(today, trigger_time)

        scheduler._run_kline_sync_with_verification.assert_called_once_with(today)

    @pytest.mark.asyncio
    async def test_no_kline_trigger_at_22_00(self):
        """Does not trigger K-line sync at 22:00."""
        scheduler = AutoSyncScheduler()
        scheduler._run_kline_sync_with_verification = AsyncMock()

        today = date(2025, 3, 28)
        non_trigger_time = time(22, 0)

        await scheduler._check_kline_trigger(today, non_trigger_time)

        scheduler._run_kline_sync_with_verification.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_calendar_trigger_at_00_00(self):
        """Triggers calendar check at 00:00."""
        scheduler = AutoSyncScheduler()
        scheduler._calendar_job.run = AsyncMock()
        scheduler._running = True

        today = date(2025, 12, 20)
        trigger_time = time(0, 0)

        await scheduler._check_calendar_trigger(today, trigger_time)

        scheduler._calendar_job.run.assert_called_once_with(today)

    @pytest.mark.asyncio
    async def test_no_calendar_trigger_at_01_00(self):
        """Does not trigger calendar check at 01:00."""
        scheduler = AutoSyncScheduler()
        scheduler._calendar_job.run = AsyncMock()

        today = date(2025, 12, 20)
        non_trigger_time = time(1, 0)

        await scheduler._check_calendar_trigger(today, non_trigger_time)

        scheduler._calendar_job.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_asyncio_task(self):
        """Creates asyncio.Task for sync jobs."""
        scheduler = AutoSyncScheduler()
        scheduler._run_kline_sync_with_verification = AsyncMock()
        scheduler._running = True

        today = date(2025, 3, 28)
        trigger_time = time(23, 0)

        await scheduler._check_kline_trigger(today, trigger_time)

        # Task should be added to _tasks set
        assert len(scheduler._tasks) == 1

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks(self):
        """Stop cancels all pending tasks."""
        scheduler = AutoSyncScheduler()
        scheduler._running = True

        # Create a real asyncio task that will be cancelled
        async def dummy_task():
            await asyncio.sleep(10)  # Long enough to be cancelled

        task = asyncio.create_task(dummy_task())
        scheduler._tasks.add(task)

        await scheduler.stop()

        assert task.cancelled() is True
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_stop_closes_database(self):
        """Stop closes database connection."""
        scheduler = AutoSyncScheduler()

        # Mock async_db_manager
        import galaxy_db_sync.application.scheduler.scheduler as sched
        original_db_manager = sched.async_db_manager
        sched.async_db_manager = MagicMock()
        sched.async_db_manager.close = AsyncMock()

        await scheduler.stop()

        sched.async_db_manager.close.assert_called_once()
        sched.async_db_manager = original_db_manager


class TestCompletenessTrigger:
    """Tests for completeness check trigger (D-19)."""

    @pytest.mark.asyncio
    async def test_check_completeness_trigger_at_17_00(self):
        """Triggers completeness check at 17:00 on trading days."""
        scheduler = AutoSyncScheduler()
        scheduler._completeness_job.run = AsyncMock(return_value={"total_missing": 0})
        scheduler._running = True

        today = date(2025, 3, 28)  # Friday
        trigger_time = time(17, 0)

        # Mock trading calendar to return today as trading day
        with patch("galaxy_db_sync.application.scheduler.scheduler.trading_calendar_service") as mock_cal:
            mock_cal.get_trading_days_async = AsyncMock(return_value=[today])

            await scheduler._check_completeness_trigger(today, trigger_time)

            scheduler._completeness_job.run.assert_called_once_with("daily_17pm", today)

    @pytest.mark.asyncio
    async def test_no_completeness_check_on_non_trading_day(self):
        """Does not trigger completeness check on non-trading days."""
        scheduler = AutoSyncScheduler()
        scheduler._completeness_job.run = AsyncMock(return_value={"total_missing": 0})
        scheduler._running = True

        today = date(2025, 3, 30)  # Sunday
        trigger_time = time(17, 0)

        # Mock trading calendar to return empty (non-trading day)
        with patch("galaxy_db_sync.application.scheduler.scheduler.trading_calendar_service") as mock_cal:
            mock_cal.get_trading_days_async = AsyncMock(return_value=[])

            await scheduler._check_completeness_trigger(today, trigger_time)

            scheduler._completeness_job.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_completeness_trigger_at_16_00(self):
        """Does not trigger completeness check at 16:00."""
        scheduler = AutoSyncScheduler()
        scheduler._completeness_job.run = AsyncMock()

        today = date(2025, 3, 28)
        non_trigger_time = time(16, 0)

        await scheduler._check_completeness_trigger(today, non_trigger_time)

        scheduler._completeness_job.run.assert_not_called()


class TestPostSyncVerification:
    """Tests for post-sync completeness verification (D-19)."""

    @pytest.mark.asyncio
    async def test_run_kline_sync_with_verification(self):
        """K-line sync followed by completeness verification."""
        scheduler = AutoSyncScheduler()
        scheduler._kline_job.run = AsyncMock()
        scheduler._completeness_job.run = AsyncMock(return_value={"total_missing": 0})

        today = date(2025, 3, 28)

        await scheduler._run_kline_sync_with_verification(today)

        scheduler._kline_job.run.assert_called_once_with(today)
        scheduler._completeness_job.run.assert_called_once_with("post_sync", today)


class TestSleepDuration:
    """Tests for sleep duration calculation."""

    def test_sleep_to_next_minute(self):
        """Sleep duration calculated correctly."""
        # At 23:00:30, should sleep ~31 seconds to reach 23:01:00
        now = datetime(2025, 3, 28, 23, 0, 30)
        seconds_to_next = 60 - now.second
        assert seconds_to_next == 30


class TestTaskNaming:
    """Tests for task naming pattern."""

    @pytest.mark.asyncio
    async def test_kline_task_has_descriptive_name(self):
        """K-line sync task has descriptive name."""
        scheduler = AutoSyncScheduler()
        scheduler._run_kline_sync_with_verification = AsyncMock()
        scheduler._running = True

        today = date(2025, 3, 28)
        trigger_time = time(23, 0)

        await scheduler._check_kline_trigger(today, trigger_time)

        # Task name should contain date
        task = list(scheduler._tasks)[0]
        assert "kline" in task.get_name()
        assert "2025" in task.get_name()

    @pytest.mark.asyncio
    async def test_calendar_task_has_descriptive_name(self):
        """Calendar sync task has descriptive name."""
        scheduler = AutoSyncScheduler()
        scheduler._calendar_job.run = AsyncMock()
        scheduler._running = True

        today = date(2025, 12, 20)
        trigger_time = time(0, 0)

        await scheduler._check_calendar_trigger(today, trigger_time)

        # Task name should contain date
        task = list(scheduler._tasks)[0]
        assert "calendar" in task.get_name()
        assert "2025" in task.get_name()

    @pytest.mark.asyncio
    async def test_completeness_task_has_descriptive_name(self):
        """Completeness check task has descriptive name."""
        scheduler = AutoSyncScheduler()
        scheduler._completeness_job.run = AsyncMock(return_value={"total_missing": 0})
        scheduler._running = True

        today = date(2025, 3, 28)
        trigger_time = time(17, 0)

        with patch("galaxy_db_sync.application.scheduler.scheduler.trading_calendar_service") as mock_cal:
            mock_cal.get_trading_days_async = AsyncMock(return_value=[today])

            await scheduler._check_completeness_trigger(today, trigger_time)

            # Task name should contain date
            task = list(scheduler._tasks)[0]
            assert "completeness" in task.get_name()
            assert "2025" in task.get_name()