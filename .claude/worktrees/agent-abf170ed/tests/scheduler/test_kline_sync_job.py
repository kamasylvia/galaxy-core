"""Tests for KlineSyncJob."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from galaxy_db_bridge.shared_kernel.enums.interval import Interval
from galaxy_db_bridge.application.scheduler.kline_sync_job import KlineSyncJob


class TestKlineSyncJobInit:
    """Tests for KlineSyncJob initialization."""

    def test_init_with_state_manager(self, mock_state_manager):
        """Initializes with state manager."""
        job = KlineSyncJob(mock_state_manager)
        assert job._state_manager is mock_state_manager


class TestGetPeriodIdentifier:
    """Tests for period identifier generation."""

    def test_day_identifier(self, mock_state_manager):
        """DAY uses YYYYMMDD format."""
        job = KlineSyncJob(mock_state_manager)
        result = job._get_period_identifier(Interval.DAY, date(2025, 3, 28))
        assert result == "20250328"

    def test_week_identifier(self, mock_state_manager):
        """WEEK uses YYYY-WN format."""
        job = KlineSyncJob(mock_state_manager)
        result = job._get_period_identifier(Interval.WEEK, date(2025, 3, 28))
        assert result == "2025-W13"  # March 28 is week 13 (ISO calendar)

    def test_month_identifier(self, mock_state_manager):
        """MONTH uses YYYY-MM format."""
        job = KlineSyncJob(mock_state_manager)
        result = job._get_period_identifier(Interval.MONTH, date(2025, 3, 15))
        assert result == "2025-03"

    def test_season_identifier(self, mock_state_manager):
        """SEASON uses YYYY-QN format."""
        job = KlineSyncJob(mock_state_manager)
        result = job._get_period_identifier(Interval.SEASON, date(2025, 3, 15))
        assert result == "2025-Q1"

    def test_year_identifier(self, mock_state_manager):
        """YEAR uses YYYY format."""
        job = KlineSyncJob(mock_state_manager)
        result = job._get_period_identifier(Interval.YEAR, date(2025, 12, 31))
        assert result == "2025"


class TestKlineSyncJobRun:
    """Tests for KlineSyncJob.run method."""

    @pytest.mark.asyncio
    async def test_skips_already_synced(self, mock_state_manager, mock_boundary_checker):
        """Skips periods that are already synced."""
        mock_state_manager.is_synced.return_value = True
        mock_boundary_checker.get_periods_to_sync_today.return_value = [Interval.DAY]

        job = KlineSyncJob(mock_state_manager)
        job._boundary_checker = mock_boundary_checker

        await job.run(date(2025, 3, 28))

        # Should not call mark_running since already synced
        mock_state_manager.mark_running.assert_not_called()

    @pytest.mark.asyncio
    async def test_marks_running_before_sync(self, mock_state_manager, mock_boundary_checker):
        """Marks sync as running before execution."""
        mock_state_manager.is_synced.return_value = False
        mock_boundary_checker.get_periods_to_sync_today.return_value = [Interval.DAY]

        job = KlineSyncJob(mock_state_manager)
        job._boundary_checker = mock_boundary_checker
        job._do_sync = AsyncMock(return_value=None)

        await job.run(date(2025, 3, 28))

        mock_state_manager.mark_running.assert_called_once_with("kline_day", "20250328")

    @pytest.mark.asyncio
    async def test_marks_success_after_sync(self, mock_state_manager, mock_boundary_checker):
        """Marks sync as success after successful execution."""
        mock_state_manager.is_synced.return_value = False
        mock_boundary_checker.get_periods_to_sync_today.return_value = [Interval.DAY]

        job = KlineSyncJob(mock_state_manager)
        job._boundary_checker = mock_boundary_checker
        job._do_sync = AsyncMock(return_value=None)

        await job.run(date(2025, 3, 28))

        mock_state_manager.mark_success.assert_called_once_with("kline_day", "20250328")

    @pytest.mark.asyncio
    async def test_marks_failed_after_sync_failure(self, mock_state_manager, mock_boundary_checker):
        """Marks sync as failed after all retries exhausted."""
        mock_state_manager.is_synced.return_value = False
        mock_boundary_checker.get_periods_to_sync_today.return_value = [Interval.DAY]

        job = KlineSyncJob(mock_state_manager)
        job._boundary_checker = mock_boundary_checker
        # Mock sync_with_retry to return False (all retries exhausted)
        with patch("galaxy_db_bridge.application.scheduler.kline_sync_job.sync_with_retry", return_value=False):
            await job.run(date(2025, 3, 28))

        mock_state_manager.mark_failed.assert_called_once_with(
            "kline_day", "20250328", "All retries exhausted"
        )

    @pytest.mark.asyncio
    async def test_syncs_day_and_week_on_friday(self, mock_state_manager, mock_boundary_checker):
        """Syncs DAY and WEEK intervals on Friday (week ending)."""
        mock_state_manager.is_synced.return_value = False
        # Friday March 28, 2025 - both DAY and WEEK end
        mock_boundary_checker.get_periods_to_sync_today.return_value = [
            Interval.DAY, Interval.WEEK
        ]

        job = KlineSyncJob(mock_state_manager)
        job._boundary_checker = mock_boundary_checker
        job._do_sync = AsyncMock(return_value=None)

        await job.run(date(2025, 3, 28))

        # Should sync both intervals in order: DAY first, then WEEK
        assert mock_state_manager.mark_running.call_count == 2
        mock_state_manager.mark_running.assert_any_call("kline_day", "20250328")
        mock_state_manager.mark_running.assert_any_call("kline_week", "2025-W13")

    @pytest.mark.asyncio
    async def test_no_intervals_to_sync(self, mock_state_manager, mock_boundary_checker):
        """Handles case where no intervals need syncing."""
        mock_boundary_checker.get_periods_to_sync_today.return_value = []

        job = KlineSyncJob(mock_state_manager)
        job._boundary_checker = mock_boundary_checker

        await job.run(date(2025, 3, 28))

        mock_state_manager.mark_running.assert_not_called()
        mock_state_manager.mark_success.assert_not_called()
        mock_state_manager.mark_failed.assert_not_called()

    @pytest.mark.asyncio
    async def test_filters_by_enabled_intervals(self, mock_state_manager, mock_boundary_checker):
        """Only syncs intervals that are enabled in config."""
        mock_state_manager.is_synced.return_value = False
        mock_boundary_checker.get_periods_to_sync_today.return_value = [
            Interval.DAY, Interval.WEEK, Interval.MONTH
        ]

        job = KlineSyncJob(mock_state_manager)
        job._boundary_checker = mock_boundary_checker
        job._do_sync = AsyncMock(return_value=None)
        # Mock config to only enable DAY
        job._config = {"enabled_intervals": ["day"]}

        await job.run(date(2025, 3, 28))

        # Only DAY should be synced
        mock_state_manager.mark_running.assert_called_once_with("kline_day", "20250328")