"""Tests for KlineSyncJob.

Tests verify KlineSyncJob uses resolve_symbols + prepare_sync_args from
sync_common (D-08), with short periods passing start=None to rely on
last_sync_date, and long periods using _get_period_dates.
"""

from datetime import date
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from galaxy_core.application.scheduler.kline_sync_job import KlineSyncJob
from galaxy_core.shared_kernel.enums.interval import Interval


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


class TestKlineSyncJobRunMinute:
    """Tests for KlineSyncJob.run_minute."""

    @pytest.mark.asyncio
    async def test_run_minute_syncs_enabled_intervals(self, mock_state_manager):
        """Syncs all enabled minute intervals."""
        mock_state_manager.is_synced.return_value = False

        job = KlineSyncJob(mock_state_manager)
        job._config = {"enabled_intervals": ["min1", "min5", "day"], "security_types": ["SH_A"]}
        job._do_sync = AsyncMock(return_value=None)

        await job.run_minute(date(2025, 3, 29))

        # MIN1 and MIN5 should be synced (MIN3, MIN10 etc. not enabled)
        assert mock_state_manager.mark_running.call_count == 2
        mock_state_manager.mark_running.assert_any_call("kline_min1", "20250328")
        mock_state_manager.mark_running.assert_any_call("kline_min5", "20250328")

    @pytest.mark.asyncio
    async def test_run_minute_skips_when_none_enabled(self, mock_state_manager):
        """Skips when no minute intervals are enabled."""
        job = KlineSyncJob(mock_state_manager)
        job._config = {"enabled_intervals": ["day"], "security_types": ["SH_A"]}
        job._do_sync = AsyncMock(return_value=None)

        await job.run_minute(date(2025, 3, 29))

        job._do_sync.assert_not_called()
        mock_state_manager.mark_running.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_minute_failure_non_blocking(self, mock_state_manager):
        """Failure in one minute interval does not block others."""
        mock_state_manager.is_synced.return_value = False

        job = KlineSyncJob(mock_state_manager)
        job._config = {"enabled_intervals": ["min1", "min5"], "security_types": ["SH_A"]}

        # First call (MIN1) fails, retry succeeds; MIN5 succeeds on first try
        job._do_sync = AsyncMock(side_effect=[ValueError("MIN1 failed"), None, None])

        await job.run_minute(date(2025, 3, 29))

        # MIN1: initial fail + retry success = 2 calls; MIN5: 1 call = 3 total
        assert job._do_sync.call_count == 3


class TestKlineSyncJobRunDay:
    """Tests for KlineSyncJob.run_day."""

    @pytest.mark.asyncio
    async def test_run_day_syncs_day(self, mock_state_manager):
        """Syncs daily K-line."""
        mock_state_manager.is_synced.return_value = False

        job = KlineSyncJob(mock_state_manager)
        job._config = {"enabled_intervals": ["day"], "security_types": ["SH_A"]}
        job._do_sync = AsyncMock(return_value=None)

        await job.run_day(date(2025, 3, 29))

        mock_state_manager.mark_running.assert_called_once_with("kline_day", "20250328")

    @pytest.mark.asyncio
    async def test_run_day_skips_when_disabled(self, mock_state_manager):
        """Skips when day is not enabled."""
        job = KlineSyncJob(mock_state_manager)
        job._config = {"enabled_intervals": ["week"], "security_types": ["SH_A"]}
        job._do_sync = AsyncMock(return_value=None)

        await job.run_day(date(2025, 3, 29))

        job._do_sync.assert_not_called()


class TestKlineSyncJobRunLongIntervals:
    """Tests for KlineSyncJob.run_week/month/season/year."""

    @pytest.mark.asyncio
    async def test_run_week_when_last_trading_day(self, mock_state_manager, mock_boundary_checker):
        """Syncs week when yesterday was last trading day of week."""
        mock_state_manager.is_synced.return_value = False
        mock_boundary_checker.is_last_trading_day_of_period.return_value = True

        job = KlineSyncJob(mock_state_manager)
        job._boundary_checker = mock_boundary_checker
        job._config = {"enabled_intervals": ["week"], "security_types": ["SH_A"]}
        job._do_sync = AsyncMock(return_value=None)

        await job.run_week(date(2025, 3, 29))

        mock_boundary_checker.is_last_trading_day_of_period.assert_called_once_with(
            Interval.WEEK, date(2025, 3, 28)
        )
        mock_state_manager.mark_running.assert_called_once_with("kline_week", "2025-W13")

    @pytest.mark.asyncio
    async def test_run_week_skips_when_not_last_trading_day(
        self, mock_state_manager, mock_boundary_checker
    ):
        """Skips week when yesterday was not last trading day."""
        mock_boundary_checker.is_last_trading_day_of_period.return_value = False

        job = KlineSyncJob(mock_state_manager)
        job._boundary_checker = mock_boundary_checker
        job._config = {"enabled_intervals": ["week"], "security_types": ["SH_A"]}
        job._do_sync = AsyncMock(return_value=None)

        await job.run_week(date(2025, 3, 29))

        job._do_sync.assert_not_called()
        mock_state_manager.mark_running.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_week_skips_when_disabled(self, mock_state_manager, mock_boundary_checker):
        """Skips week when not in enabled_intervals."""
        mock_boundary_checker.is_last_trading_day_of_period.return_value = True

        job = KlineSyncJob(mock_state_manager)
        job._boundary_checker = mock_boundary_checker
        job._config = {"enabled_intervals": ["day"], "security_types": ["SH_A"]}
        job._do_sync = AsyncMock(return_value=None)

        await job.run_week(date(2025, 3, 29))

        job._do_sync.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_month_when_last_trading_day(self, mock_state_manager, mock_boundary_checker):
        """Syncs month when yesterday was last trading day of month."""
        mock_state_manager.is_synced.return_value = False
        mock_boundary_checker.is_last_trading_day_of_period.return_value = True

        job = KlineSyncJob(mock_state_manager)
        job._boundary_checker = mock_boundary_checker
        job._config = {"enabled_intervals": ["month"], "security_types": ["SH_A"]}
        job._do_sync = AsyncMock(return_value=None)

        await job.run_month(date(2025, 3, 29))

        mock_state_manager.mark_running.assert_called_once_with("kline_month", "2025-03")

    @pytest.mark.asyncio
    async def test_run_season_when_last_trading_day(
        self, mock_state_manager, mock_boundary_checker
    ):
        """Syncs season when yesterday was last trading day of quarter."""
        mock_state_manager.is_synced.return_value = False
        mock_boundary_checker.is_last_trading_day_of_period.return_value = True

        job = KlineSyncJob(mock_state_manager)
        job._boundary_checker = mock_boundary_checker
        job._config = {"enabled_intervals": ["season"], "security_types": ["SH_A"]}
        job._do_sync = AsyncMock(return_value=None)

        await job.run_season(date(2025, 3, 31))

        mock_state_manager.mark_running.assert_called_once_with("kline_season", "2025-Q1")

    @pytest.mark.asyncio
    async def test_run_year_when_last_trading_day(self, mock_state_manager, mock_boundary_checker):
        """Syncs year when yesterday was last trading day of year."""
        mock_state_manager.is_synced.return_value = False
        mock_boundary_checker.is_last_trading_day_of_period.return_value = True

        job = KlineSyncJob(mock_state_manager)
        job._boundary_checker = mock_boundary_checker
        job._config = {"enabled_intervals": ["year"], "security_types": ["SH_A"]}
        job._do_sync = AsyncMock(return_value=None)

        await job.run_year(date(2026, 1, 1))

        mock_state_manager.mark_running.assert_called_once_with("kline_year", "2025")

    @pytest.mark.asyncio
    async def test_long_interval_failure_non_blocking(
        self, mock_state_manager, mock_boundary_checker
    ):
        """Failure in long interval is logged but not raised."""
        mock_state_manager.is_synced.return_value = False
        mock_boundary_checker.is_last_trading_day_of_period.return_value = True

        job = KlineSyncJob(mock_state_manager)
        job._boundary_checker = mock_boundary_checker
        job._config = {"enabled_intervals": ["week"], "security_types": ["SH_A"]}
        job._do_sync = AsyncMock(side_effect=ValueError("sync failed"))

        # Patch asyncio.sleep to avoid 15-minute retry delays
        with patch("galaxy_core.application.scheduler.retry_handler.asyncio.sleep", new_callable=AsyncMock):
            await job.run_week(date(2025, 3, 29))

        # 1 initial + 3 retries = 4 calls
        assert job._do_sync.call_count == 4


class TestKlineSyncJobRun:
    """Tests for KlineSyncJob.run (backward compatibility, calls all periods)."""

    @pytest.mark.asyncio
    async def test_run_calls_all_period_methods(self, mock_state_manager, mock_boundary_checker):
        """run() calls run_minute, run_day, run_week, run_month, run_season, run_year."""
        job = KlineSyncJob(mock_state_manager)
        job._boundary_checker = mock_boundary_checker
        job.run_minute = AsyncMock()
        job.run_day = AsyncMock()
        job.run_week = AsyncMock()
        job.run_month = AsyncMock()
        job.run_season = AsyncMock()
        job.run_year = AsyncMock()

        await job.run(date(2025, 3, 29))

        job.run_minute.assert_called_once_with(date(2025, 3, 29))
        job.run_day.assert_called_once_with(date(2025, 3, 29))
        job.run_week.assert_called_once_with(date(2025, 3, 29))
        job.run_month.assert_called_once_with(date(2025, 3, 29))
        job.run_season.assert_called_once_with(date(2025, 3, 29))
        job.run_year.assert_called_once_with(date(2025, 3, 29))


class TestDoSync:
    """Tests for _do_sync using resolve_symbols + prepare_sync_args (D-08)."""

    @pytest.mark.asyncio
    async def test_do_sync_calls_resolve_symbols(self, mock_state_manager):
        """_do_sync should call resolve_symbols with security type name."""
        mock_ref_provider = MagicMock()
        mock_ref_provider.get_hist_code_list = AsyncMock(return_value=["600000", "600001"])

        mock_kline_service = MagicMock()
        mock_kline_service.sync = AsyncMock(return_value=MagicMock(
            synced_records=10, success_count=2, failed_codes=[], total_symbols=2
        ))

        job = KlineSyncJob(
            mock_state_manager,
            kline_service=mock_kline_service,
            reference_provider=mock_ref_provider,
        )
        job._config = {"security_types": ["SH_A"], "enabled_intervals": ["day"]}

        with patch("galaxy_core.application.scheduler.kline_sync_job.resolve_symbols",
                    new_callable=AsyncMock, return_value=["600000", "600001"]) as mock_resolve:
            await job._do_sync(Interval.DAY, date(2025, 3, 28))

            mock_resolve.assert_called_once_with(
                ["SH_A"], mock_ref_provider, date(2025, 3, 28)
            )

    @pytest.mark.asyncio
    async def test_do_sync_short_period_passes_none_start(self, mock_state_manager):
        """_do_sync for short period (DAY) passes start=None to rely on last_sync_date (D-08)."""
        mock_ref_provider = MagicMock()
        mock_kline_service = MagicMock()
        mock_kline_service.sync = AsyncMock(return_value=MagicMock(
            synced_records=5, success_count=2, failed_codes=[], total_symbols=2
        ))

        job = KlineSyncJob(
            mock_state_manager,
            kline_service=mock_kline_service,
            reference_provider=mock_ref_provider,
        )
        job._config = {"security_types": ["SH_A"], "enabled_intervals": ["day"]}

        with patch("galaxy_core.application.scheduler.kline_sync_job.resolve_symbols",
                    new_callable=AsyncMock, return_value=["600000", "600001"]):
            await job._do_sync(Interval.DAY, date(2025, 3, 28))

        # kline_service.sync called with start=None (relies on last_sync_date)
        mock_kline_service.sync.assert_called_once()
        call_kwargs = mock_kline_service.sync.call_args.kwargs
        assert call_kwargs["symbols"] == ["600000", "600001"]
        assert call_kwargs["start"] is None
        assert call_kwargs["end"] is not None

    @pytest.mark.asyncio
    async def test_do_sync_long_period_passes_calculated_dates(self, mock_state_manager):
        """_do_sync for long period (WEEK) passes _get_period_dates calculated start."""
        mock_ref_provider = MagicMock()
        mock_kline_service = MagicMock()
        mock_kline_service.sync = AsyncMock(return_value=MagicMock(
            synced_records=10, success_count=2, failed_codes=[], total_symbols=2
        ))

        job = KlineSyncJob(
            mock_state_manager,
            kline_service=mock_kline_service,
            reference_provider=mock_ref_provider,
        )
        job._config = {"security_types": ["SH_A"], "enabled_intervals": ["week"]}

        with patch("galaxy_core.application.scheduler.kline_sync_job.resolve_symbols",
                    new_callable=AsyncMock, return_value=["600000", "600001"]):
            # Friday March 28, 2025 -- week starts Monday March 24
            await job._do_sync(Interval.WEEK, date(2025, 3, 28))

        mock_kline_service.sync.assert_called_once()
        call_kwargs = mock_kline_service.sync.call_args.kwargs
        assert call_kwargs["symbols"] == ["600000", "600001"]
        # Long period: start is not None (calculated by _get_period_dates)
        assert call_kwargs["start"] is not None
        assert call_kwargs["end"] is not None

    @pytest.mark.asyncio
    async def test_do_sync_calls_reference_provider_via_resolve_symbols(self, mock_state_manager):
        """_do_sync calls reference_provider.get_hist_code_list via resolve_symbols."""
        mock_ref_provider = MagicMock()
        mock_ref_provider.get_hist_code_list = AsyncMock(return_value=["600000", "600001"])

        mock_kline_service = MagicMock()
        mock_kline_service.sync = AsyncMock(return_value=MagicMock(
            synced_records=10, success_count=2, failed_codes=[], total_symbols=2
        ))

        job = KlineSyncJob(
            mock_state_manager,
            kline_service=mock_kline_service,
            reference_provider=mock_ref_provider,
        )
        job._config = {"security_types": ["SH_A"], "enabled_intervals": ["day"]}

        await job._do_sync(Interval.DAY, date(2025, 3, 28))

        # resolve_symbols internally calls get_hist_code_list
        mock_ref_provider.get_hist_code_list.assert_called_once_with(
            security_type="SH_A",
            start_date=20250328,
            end_date=20250328,
            local_path=ANY,
        )


class TestGetPeriodDates:
    """Tests for _get_period_dates method (long intervals only)."""

    @pytest.mark.asyncio
    async def test_week_period_dates(self, mock_state_manager):
        """WEEK interval should return Monday to today."""
        job = KlineSyncJob(mock_state_manager)
        # Friday March 28, 2025
        friday = date(2025, 3, 28)
        start, end = await job._get_period_dates(Interval.WEEK, friday)

        # Monday of that week is March 24
        assert start == date(2025, 3, 24)
        assert end == friday

    @pytest.mark.asyncio
    async def test_month_period_dates(self, mock_state_manager):
        """MONTH interval should return first of month to today."""
        job = KlineSyncJob(mock_state_manager)
        target_date = date(2025, 3, 28)
        start, end = await job._get_period_dates(Interval.MONTH, target_date)

        assert start == date(2025, 3, 1)
        assert end == target_date

    @pytest.mark.asyncio
    async def test_season_period_dates(self, mock_state_manager):
        """SEASON interval should return quarter start to today."""
        job = KlineSyncJob(mock_state_manager)
        target_date = date(2025, 5, 15)
        start, end = await job._get_period_dates(Interval.SEASON, target_date)

        # Q2 starts April 1
        assert start == date(2025, 4, 1)
        assert end == target_date

    @pytest.mark.asyncio
    async def test_year_period_dates(self, mock_state_manager):
        """YEAR interval should return Jan 1 to today."""
        job = KlineSyncJob(mock_state_manager)
        target_date = date(2025, 6, 15)
        start, end = await job._get_period_dates(Interval.YEAR, target_date)

        assert start == date(2025, 1, 1)
        assert end == target_date


def test_minute_security_types_scoping():
    """分钟定稿只覆盖 ETF(2026-10-27 裁决):minute_security_types 独立生效. """
    job = KlineSyncJob.__new__(KlineSyncJob)
    job._config = {
        "security_types": ["EXTRA_ETF", "EXTRA_STOCK_A", "EXTRA_INDEX_A"],
        "minute_security_types": ["EXTRA_ETF"],
    }
    assert job._security_types_for(Interval.MIN1) == ["EXTRA_ETF"]
    assert job._security_types_for(Interval.MIN5) == ["EXTRA_ETF"]
    assert job._security_types_for(Interval.DAY) == [
        "EXTRA_ETF",
        "EXTRA_STOCK_A",
        "EXTRA_INDEX_A",
    ]


def test_minute_security_types_fallback_to_full_list():
    """未配置 minute_security_types 时回落全集(旧行为保持)."""
    job = KlineSyncJob.__new__(KlineSyncJob)
    job._config = {"security_types": ["EXTRA_STOCK_A"]}
    assert job._security_types_for(Interval.MIN1) == ["EXTRA_STOCK_A"]
