"""Tests for CompletenessCheckJob."""

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from galaxy_db_sync.shared_kernel.enums.interval import Interval
from galaxy_db_sync.shared_kernel.enums.security_type import SecurityType
from galaxy_db_sync.application.scheduler.completeness_check_job import CompletenessCheckJob


class TestCompletenessCheckJobInit:
    """Tests for CompletenessCheckJob initialization."""

    def test_init_creates_checker(self, mock_state_manager):
        """Job should create KlineCompletenessChecker."""
        job = CompletenessCheckJob(mock_state_manager)
        assert job._checker is not None
        assert job._state_manager == mock_state_manager

    def test_init_loads_config(self, mock_state_manager):
        """Job should load scheduler config."""
        job = CompletenessCheckJob(mock_state_manager)
        assert job._config is not None

    def test_init_loads_routine_lookback(self, mock_state_manager):
        """Job should load routine_lookback_periods config."""
        job = CompletenessCheckJob(mock_state_manager)
        assert job._routine_lookback == 10  # default in conftest

    def test_init_creates_listing_dates_cache(self, mock_state_manager):
        """Job should create empty listing dates cache."""
        job = CompletenessCheckJob(mock_state_manager)
        assert job._listing_dates_cache == {}


class TestCompletenessCheckJobRun:
    """Tests for CompletenessCheckJob.run()."""

    @pytest.mark.asyncio
    async def test_run_returns_results(self, mock_state_manager):
        """run() should return check results dict."""
        job = CompletenessCheckJob(mock_state_manager)

        # Mock symbol list
        symbols_df = MagicMock()
        symbols_df.__getitem__ = MagicMock(return_value=MagicMock())
        symbols_df.__getitem__.return_value.tolist = MagicMock(return_value=["600000", "600001"])
        job._config = {
            "check_intervals": ["day"],
            "security_type": "SH_A",
            "check_ranges": {"SH_A": {"start_year": 2013}, "default": {"start_year": 2013}},
            "routine_lookback_periods": 10,
        }

        with patch.object(job, "_check_interval", new_callable=AsyncMock) as mock_check:
            with patch.object(job, "_repair_missing", new_callable=AsyncMock) as mock_repair:
                with patch.object(
                    job, "_fetch_listing_dates", new_callable=AsyncMock
                ) as mock_fetch_listing:
                    with patch(
                        "galaxy_db_sync.application.scheduler.completeness_check_job.amazing_data_client"
                    ) as mock_client:
                        with patch(
                            "galaxy_db_sync.application.scheduler.completeness_check_job.completeness_check_log_manager"
                        ) as mock_log_mgr:
                            mock_client.get_stock_list_async = AsyncMock(return_value=symbols_df)
                            mock_check.return_value = {"missing_count": 0, "missing_symbols": []}
                            mock_log_mgr.create_log = AsyncMock(return_value=MagicMock(id=1))
                            mock_log_mgr.complete_log = AsyncMock()

                            result = await job.run(
                                "daily_17pm", date(2025, 3, 28), check_mode="routine"
                            )

                            assert "total_missing" in result
                            assert "repair_triggered" in result
                            assert "intervals_checked" in result
                            assert "check_mode" in result
                            assert result["check_mode"] == "routine"

    @pytest.mark.asyncio
    async def test_run_checks_multiple_intervals(self, mock_state_manager):
        """run() should check all configured intervals."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {
            "check_intervals": ["day", "week"],
            "security_type": "SH_A",
            "check_ranges": {"SH_A": {"start_year": 2013}, "default": {"start_year": 2013}},
            "routine_lookback_periods": 10,
        }

        symbols_df = MagicMock()
        symbols_df.__getitem__ = MagicMock(return_value=MagicMock())
        symbols_df.__getitem__.return_value.tolist = MagicMock(return_value=["600000"])

        with patch.object(job, "_check_interval", new_callable=AsyncMock) as mock_check:
            with patch.object(job, "_repair_missing", new_callable=AsyncMock) as mock_repair:
                with patch.object(
                    job, "_fetch_listing_dates", new_callable=AsyncMock
                ) as mock_fetch_listing:
                    with patch(
                        "galaxy_db_sync.application.scheduler.completeness_check_job.amazing_data_client"
                    ) as mock_client:
                        with patch(
                            "galaxy_db_sync.application.scheduler.completeness_check_job.completeness_check_log_manager"
                        ) as mock_log_mgr:
                            mock_client.get_stock_list_async = AsyncMock(return_value=symbols_df)
                            mock_check.return_value = {"missing_count": 0, "missing_symbols": []}
                            mock_log_mgr.create_log = AsyncMock(return_value=MagicMock(id=1))
                            mock_log_mgr.complete_log = AsyncMock()

                            await job.run("daily_17pm", date(2025, 3, 28), check_mode="routine")

                            # Should be called for both intervals
                            assert mock_check.call_count == 2

    @pytest.mark.asyncio
    async def test_run_triggers_repair_when_missing(self, mock_state_manager):
        """run() should trigger repair when missing data found."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {
            "check_intervals": ["day"],
            "security_type": "SH_A",
            "check_ranges": {"SH_A": {"start_year": 2013}, "default": {"start_year": 2013}},
            "routine_lookback_periods": 10,
        }

        symbols_df = MagicMock()
        symbols_df.__getitem__ = MagicMock(return_value=MagicMock())
        symbols_df.__getitem__.return_value.tolist = MagicMock(return_value=["600000"])

        with patch.object(job, "_check_interval", new_callable=AsyncMock) as mock_check:
            with patch.object(job, "_repair_missing", new_callable=AsyncMock) as mock_repair:
                with patch.object(
                    job, "_fetch_listing_dates", new_callable=AsyncMock
                ) as mock_fetch_listing:
                    with patch(
                        "galaxy_db_sync.application.scheduler.completeness_check_job.amazing_data_client"
                    ) as mock_client:
                        with patch(
                            "galaxy_db_sync.application.scheduler.completeness_check_job.completeness_check_log_manager"
                        ) as mock_log_mgr:
                            mock_client.get_stock_list_async = AsyncMock(return_value=symbols_df)
                            mock_check.return_value = {
                                "missing_count": 10,
                                "missing_symbols": [("600000", [])],
                            }
                            mock_repair.return_value = {"success": True, "records_synced": 10}
                            mock_log_mgr.create_log = AsyncMock(return_value=MagicMock(id=1))
                            mock_log_mgr.complete_log = AsyncMock()

                            result = await job.run(
                                "daily_17pm", date(2025, 3, 28), check_mode="routine"
                            )

                            assert result["repair_triggered"] == "yes"
                            mock_repair.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_full_mode(self, mock_state_manager):
        """run() should accept 'full' check_mode."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {
            "check_intervals": ["day"],
            "security_type": "SH_A",
            "check_ranges": {"SH_A": {"start_year": 2013}, "default": {"start_year": 2013}},
            "routine_lookback_periods": 10,
        }

        symbols_df = MagicMock()
        symbols_df.__getitem__ = MagicMock(return_value=MagicMock())
        symbols_df.__getitem__.return_value.tolist = MagicMock(return_value=["600000"])

        with patch.object(job, "_check_interval", new_callable=AsyncMock) as mock_check:
            with patch.object(job, "_repair_missing", new_callable=AsyncMock) as mock_repair:
                with patch.object(
                    job, "_fetch_listing_dates", new_callable=AsyncMock
                ) as mock_fetch_listing:
                    with patch(
                        "galaxy_db_sync.application.scheduler.completeness_check_job.amazing_data_client"
                    ) as mock_client:
                        with patch(
                            "galaxy_db_sync.application.scheduler.completeness_check_job.completeness_check_log_manager"
                        ) as mock_log_mgr:
                            mock_client.get_stock_list_async = AsyncMock(return_value=symbols_df)
                            mock_check.return_value = {"missing_count": 0, "missing_symbols": []}
                            mock_log_mgr.create_log = AsyncMock(return_value=MagicMock(id=1))
                            mock_log_mgr.complete_log = AsyncMock()

                            result = await job.run(
                                "daily_17pm", date(2025, 3, 28), check_mode="full"
                            )

                            assert result["check_mode"] == "full"


class TestCompletenessCheckJobCheckInterval:
    """Tests for _check_interval method."""

    @pytest.mark.asyncio
    async def test_check_interval_returns_missing_count(self, mock_state_manager):
        """_check_interval should return missing count."""
        job = CompletenessCheckJob(mock_state_manager)
        job._listing_dates_cache = {"600000": date(2020, 1, 1)}

        # Mock checker result
        mock_result = MagicMock()
        mock_result.is_complete = False
        mock_result.missing_count = 5
        mock_result.missing_ranges = [(date(2025, 3, 20), date(2025, 3, 25))]

        with patch.object(job._checker, "check", return_value=mock_result):
            with patch.object(
                job, "_get_check_range", return_value=(date(2020, 1, 1), date(2025, 3, 28))
            ) as mock_range:
                with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                    mock_to_thread.return_value = mock_result

                    result = await job._check_interval(
                        ["600000"], Interval.DAY, date(2025, 3, 28), SecurityType.SH_A, "routine"
                    )

                    assert result["missing_count"] == 5
                    assert len(result["missing_symbols"]) == 1
                    mock_range.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_interval_skips_if_listing_date_after_end(self, mock_state_manager):
        """_check_interval should skip symbol if listing date > end_date."""
        job = CompletenessCheckJob(mock_state_manager)
        # Listing date in 2026, but check end is 2025
        job._listing_dates_cache = {"600000": date(2026, 1, 1)}

        with patch.object(
            job, "_get_check_range", return_value=(date(2026, 1, 1), date(2025, 3, 28))
        ) as mock_range:
            result = await job._check_interval(
                ["600000"], Interval.DAY, date(2025, 3, 28), SecurityType.SH_A, "routine"
            )

            assert result["missing_count"] == 0
            assert result["missing_symbols"] == []


class TestCompletenessCheckJobRepairMissing:
    """Tests for _repair_missing method."""

    @pytest.mark.asyncio
    async def test_repair_missing_returns_empty_if_no_missing(self, mock_state_manager):
        """_repair_missing should return empty result if no missing symbols."""
        job = CompletenessCheckJob(mock_state_manager)

        result = await job._repair_missing([], Interval.DAY, date(2025, 3, 28))

        assert result["success"] is True
        assert result["records_synced"] == 0

    @pytest.mark.asyncio
    async def test_repair_missing_skips_if_already_done(self, mock_state_manager):
        """_repair_missing should skip if repair already done."""
        job = CompletenessCheckJob(mock_state_manager)
        mock_state_manager.is_synced = AsyncMock(return_value=True)

        missing_symbols = [("600000", [(date(2025, 3, 20), date(2025, 3, 25))])]

        result = await job._repair_missing(missing_symbols, Interval.DAY, date(2025, 3, 28))

        assert result["success"] is True
        assert result.get("reason") == "already_repaired"

    @pytest.mark.asyncio
    async def test_repair_missing_marks_running(self, mock_state_manager):
        """_repair_missing should mark repair as running."""
        job = CompletenessCheckJob(mock_state_manager)
        mock_state_manager.is_synced = AsyncMock(return_value=False)

        missing_symbols = [("600000", [(date(2025, 3, 20), date(2025, 3, 25))])]

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = 10

            await job._repair_missing(missing_symbols, Interval.DAY, date(2025, 3, 28))

            mock_state_manager.mark_running.assert_called_once()


class TestCompletenessCheckJobCheckRange:
    """Tests for _get_check_range method with check_mode and listing date."""

    def test_get_check_range_full_mode(self, mock_state_manager):
        """_get_check_range should return data start date for full mode."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {
            "check_ranges": {
                "SH_A": {"start_year": 2013},
                "default": {"start_year": 2013},
            }
        }
        job._listing_dates_cache = {"600000": date(2020, 1, 1)}
        check_date = date(2025, 3, 28)

        start, end = job._get_check_range(
            Interval.DAY, check_date, SecurityType.SH_A, "full", "600000"
        )

        # Should use listing date (max of 2013-01-01 and 2020-01-01)
        assert start == date(2020, 1, 1)
        assert end == check_date

    def test_get_check_range_routine_mode(self, mock_state_manager):
        """_get_check_range should return calculated routine start for routine mode."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {
            "check_ranges": {"SH_A": {"start_year": 2013}},
            "routine_lookback_periods": 10,
        }
        job._listing_dates_cache = {"600000": date(2020, 1, 1)}
        job._routine_lookback = 10
        check_date = date(2025, 3, 28)

        start, end = job._get_check_range(
            Interval.DAY, check_date, SecurityType.SH_A, "routine", "600000"
        )

        # Routine start should be ~15 days ago, but listing date (2020) is earlier
        # So should use routine start
        expected_routine_start = check_date - timedelta(days=15)
        assert start >= expected_routine_start
        assert end == check_date

    def test_get_check_range_listing_date_limits_start(self, mock_state_manager):
        """_get_check_range should limit start to listing date."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {"check_ranges": {"SH_A": {"start_year": 2013}}}
        job._routine_lookback = 10
        # Listing date is 2023-01-01
        job._listing_dates_cache = {"600000": date(2023, 1, 1)}
        check_date = date(2025, 3, 28)

        start, end = job._get_check_range(
            Interval.DAY, check_date, SecurityType.SH_A, "full", "600000"
        )

        # Full mode start is 2013-01-01, but listing date 2023-01-01 is later
        assert start == date(2023, 1, 1)

    def test_get_check_range_no_listing_date(self, mock_state_manager):
        """_get_check_range should use base start if no listing date cached."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {"check_ranges": {"SH_A": {"start_year": 2013}}}
        job._routine_lookback = 10
        job._listing_dates_cache = {}  # No listing date
        check_date = date(2025, 3, 28)

        start, end = job._get_check_range(
            Interval.DAY, check_date, SecurityType.SH_A, "full", "600000"
        )

        # Should use data start date (2013)
        assert start == date(2013, 1, 1)

    def test_get_check_range_fallback_to_default(self, mock_state_manager):
        """_get_check_range should fallback to default for unconfigured security_type."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {
            "check_ranges": {
                "SH_A": {"start_year": 2013},
                "default": {"start_year": 2013},
            }
        }
        job._routine_lookback = 10
        job._listing_dates_cache = {"600001": date(2020, 1, 1)}
        check_date = date(2025, 3, 28)

        # BJ_A configured with same value as default
        start, end = job._get_check_range(
            Interval.DAY, check_date, SecurityType.BJ_A, "full", "600001"
        )

        assert start == date(2020, 1, 1)

    def test_get_check_range_day_end(self, mock_state_manager):
        """_get_check_range should return today as end for DAY interval."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {"check_ranges": {"SH_A": {"start_year": 2013}}}
        job._routine_lookback = 10
        job._listing_dates_cache = {"600000": date(2013, 1, 1)}
        check_date = date(2025, 3, 28)

        start, end = job._get_check_range(
            Interval.DAY, check_date, SecurityType.SH_A, "full", "600000"
        )

        assert end == check_date

    def test_get_check_range_month_end(self, mock_state_manager):
        """_get_check_range should return month last day for MONTH interval."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {"check_ranges": {"SH_A": {"start_year": 2013}}}
        job._routine_lookback = 10
        job._listing_dates_cache = {"600000": date(2013, 1, 1)}
        check_date = date(2025, 3, 15)

        start, end = job._get_check_range(
            Interval.MONTH, check_date, SecurityType.SH_A, "full", "600000"
        )

        assert end == date(2025, 3, 31)

    def test_get_check_range_year_end(self, mock_state_manager):
        """_get_check_range should return Dec 31 for YEAR interval."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {"check_ranges": {"SH_A": {"start_year": 2013}}}
        job._routine_lookback = 10
        job._listing_dates_cache = {"600000": date(2013, 1, 1)}
        check_date = date(2025, 6, 15)

        start, end = job._get_check_range(
            Interval.YEAR, check_date, SecurityType.SH_A, "full", "600000"
        )

        assert end == date(2025, 12, 31)


class TestCalculateRoutineStart:
    """Tests for _calculate_routine_start method."""

    def test_calculate_routine_start_day(self, mock_state_manager):
        """_calculate_routine_start should return ~15 days ago for DAY."""
        job = CompletenessCheckJob(mock_state_manager)
        job._routine_lookback = 10
        check_date = date(2025, 3, 28)

        start = job._calculate_routine_start(Interval.DAY, check_date)

        # Should be ~15 days ago (10 * 1.5)
        expected = check_date - timedelta(days=15)
        assert start == expected

    def test_calculate_routine_start_week(self, mock_state_manager):
        """_calculate_routine_start should return 10 weeks ago for WEEK."""
        job = CompletenessCheckJob(mock_state_manager)
        job._routine_lookback = 10
        check_date = date(2025, 3, 28)

        start = job._calculate_routine_start(Interval.WEEK, check_date)

        expected = check_date - timedelta(weeks=10)
        assert start == expected

    def test_calculate_routine_start_month(self, mock_state_manager):
        """_calculate_routine_start should return 10 months ago for MONTH."""
        job = CompletenessCheckJob(mock_state_manager)
        job._routine_lookback = 10
        check_date = date(2025, 3, 28)

        start = job._calculate_routine_start(Interval.MONTH, check_date)

        # 10 months before March 2025 is May 2024
        assert start.year == 2024
        assert start.month == 5
        assert start.day == 1

    def test_calculate_routine_start_year(self, mock_state_manager):
        """_calculate_routine_start should return 10 years ago for YEAR."""
        job = CompletenessCheckJob(mock_state_manager)
        job._routine_lookback = 10
        check_date = date(2025, 3, 28)

        start = job._calculate_routine_start(Interval.YEAR, check_date)

        assert start == date(2015, 1, 1)

    def test_calculate_routine_start_season(self, mock_state_manager):
        """_calculate_routine_start should return 10 quarters ago for SEASON."""
        job = CompletenessCheckJob(mock_state_manager)
        job._routine_lookback = 10
        check_date = date(2025, 3, 28)  # Q1 2025

        start = job._calculate_routine_start(Interval.SEASON, check_date)

        # 10 quarters before Q1 2025 is Q3 2022 (start month 7)
        # Q1 2025 - 10 = Q(-9) -> Q3 2022 after year adjustments
        assert start.year == 2022
        assert start.month == 7
        assert start.day == 1


class TestGetDataStartDate:
    """Tests for _get_data_start_date method."""

    def test_get_data_start_date_from_config(self, mock_state_manager):
        """_get_data_start_date should return config start_year."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {"check_ranges": {"SH_A": {"start_year": 2013}}}

        start = job._get_data_start_date(SecurityType.SH_A)

        assert start == date(2013, 1, 1)

    def test_get_data_start_date_fallback_to_default(self, mock_state_manager):
        """_get_data_start_date should fallback to default config."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {
            "check_ranges": {
                "SH_A": {"start_year": 2013},
                "default": {"start_year": 2013},
            }
        }

        start = job._get_data_start_date(SecurityType.BJ_A)

        # BJ_A not explicitly configured, uses default
        assert start == date(2013, 1, 1)

    def test_get_data_start_date_default_2013_if_no_config(self, mock_state_manager):
        """_get_data_start_date should default to 2013 if no check_ranges config."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {}

        start = job._get_data_start_date(SecurityType.SH_A)

        assert start == date(2013, 1, 1)


class TestFetchListingDates:
    """Tests for _fetch_listing_dates method."""

    @pytest.mark.asyncio
    async def test_fetch_listing_dates_caches_results(self, mock_state_manager):
        """_fetch_listing_dates should cache listing dates."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {"check_ranges": {"SH_A": {"start_year": 2013}}}

        listing_dates_dict = {"600000": "20200101", "600001": "20210315"}

        with patch(
            "galaxy_db_sync.application.scheduler.completeness_check_job.amazing_data_client"
        ) as mock_client:
            mock_client.get_listing_dates_async = AsyncMock(return_value=listing_dates_dict)

            await job._fetch_listing_dates(["600000", "600001"], SecurityType.SH_A)

            assert job._listing_dates_cache["600000"] == date(2020, 1, 1)
            assert job._listing_dates_cache["600001"] == date(2021, 3, 15)

    @pytest.mark.asyncio
    async def test_fetch_listing_dates_handles_missing_date(self, mock_state_manager):
        """_fetch_listing_dates should use data start for missing listing dates."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {"check_ranges": {"SH_A": {"start_year": 2013}}}

        # One symbol has listing date, one doesn't
        listing_dates_dict = {"600000": "20200101", "600001": None}

        with patch(
            "galaxy_db_sync.application.scheduler.completeness_check_job.amazing_data_client"
        ) as mock_client:
            mock_client.get_listing_dates_async = AsyncMock(return_value=listing_dates_dict)

            await job._fetch_listing_dates(["600000", "600001"], SecurityType.SH_A)

            assert job._listing_dates_cache["600000"] == date(2020, 1, 1)
            assert job._listing_dates_cache["600001"] == date(2013, 1, 1)  # data start

    @pytest.mark.asyncio
    async def test_fetch_listing_dates_handles_api_failure(self, mock_state_manager):
        """_fetch_listing_dates should use data start on API failure."""
        job = CompletenessCheckJob(mock_state_manager)
        job._config = {"check_ranges": {"SH_A": {"start_year": 2013}}}

        with patch(
            "galaxy_db_sync.application.scheduler.completeness_check_job.amazing_data_client"
        ) as mock_client:
            mock_client.get_listing_dates_async = AsyncMock(side_effect=Exception("API failed"))

            await job._fetch_listing_dates(["600000", "600001"], SecurityType.SH_A)

            # Should fall back to data start date for all symbols
            assert job._listing_dates_cache["600000"] == date(2013, 1, 1)
            assert job._listing_dates_cache["600001"] == date(2013, 1, 1)


class TestGetPeriodEnd:
    """Tests for _get_period_end method."""

    def test_get_period_end_day(self, mock_state_manager):
        """_get_period_end should return same day for DAY."""
        job = CompletenessCheckJob(mock_state_manager)
        result = job._get_period_end(Interval.DAY, date(2025, 3, 28))
        assert result == date(2025, 3, 28)

    def test_get_period_end_month(self, mock_state_manager):
        """_get_period_end should return last day of month."""
        job = CompletenessCheckJob(mock_state_manager)
        result = job._get_period_end(Interval.MONTH, date(2025, 2, 15))
        assert result == date(2025, 2, 28)

    def test_get_period_end_year(self, mock_state_manager):
        """_get_period_end should return Dec 31."""
        job = CompletenessCheckJob(mock_state_manager)
        result = job._get_period_end(Interval.YEAR, date(2025, 6, 15))
        assert result == date(2025, 12, 31)

    def test_get_period_end_season(self, mock_state_manager):
        """_get_period_end should return last day of quarter."""
        job = CompletenessCheckJob(mock_state_manager)
        result = job._get_period_end(Interval.SEASON, date(2025, 2, 15))  # Q1 ends March 31
        assert result == date(2025, 3, 31)
