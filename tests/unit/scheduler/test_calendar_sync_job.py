"""Tests for CalendarSyncJob."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from galaxy_core.application.scheduler.calendar_sync_job import CalendarSyncJob


class TestCalendarSyncJobRun:
    """Tests for CalendarSyncJob.run method."""

    @pytest.mark.asyncio
    async def test_december_20_syncs_next_year(self, mock_state_manager):
        """Dec 20 triggers next year calendar sync."""
        mock_state_manager.is_synced.return_value = False
        mock_state_manager.mark_running = AsyncMock()
        mock_state_manager.mark_success = AsyncMock()

        job = CalendarSyncJob(mock_state_manager)
        job._do_sync_calendar = AsyncMock()
        job._check_calendar_exists = AsyncMock(return_value=False)

        await job.run(date(2025, 12, 20))

        mock_state_manager.mark_running.assert_called_once_with("calendar", "2026")

    @pytest.mark.asyncio
    async def test_december_25_checks_and_syncs_if_missing(self, mock_state_manager):
        """Dec 25 checks if next year exists, syncs if missing."""
        mock_state_manager.is_synced.return_value = False

        job = CalendarSyncJob(mock_state_manager)
        job._check_calendar_exists = AsyncMock(return_value=False)
        job._do_sync_calendar = AsyncMock()

        await job.run(date(2025, 12, 25))

        job._check_calendar_exists.assert_called_once_with(2026)

    @pytest.mark.asyncio
    async def test_december_25_skips_if_exists(self, mock_state_manager):
        """Dec 25 skips if next year calendar already exists."""
        job = CalendarSyncJob(mock_state_manager)
        job._check_calendar_exists = AsyncMock(return_value=True)
        job._do_sync_calendar = AsyncMock()

        await job.run(date(2025, 12, 25))

        job._do_sync_calendar.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_december_skips(self, mock_state_manager):
        """Non-December dates skip sync."""
        job = CalendarSyncJob(mock_state_manager)
        job._check_calendar_exists = AsyncMock(return_value=True)

        await job.run(date(2025, 11, 15))

        # Should not call any sync methods
        job._check_calendar_exists.assert_not_called()

    @pytest.mark.asyncio
    async def test_before_dec_20_skips(self, mock_state_manager):
        """Before Dec 20 skips."""
        job = CalendarSyncJob(mock_state_manager)
        job._check_calendar_exists = AsyncMock(return_value=True)

        await job.run(date(2025, 12, 15))

        job._check_calendar_exists.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_already_synced(self, mock_state_manager):
        """Skips if already synced."""
        mock_state_manager.is_synced.return_value = True

        job = CalendarSyncJob(mock_state_manager)
        job._check_calendar_exists = AsyncMock(return_value=False)
        job._do_sync_calendar = AsyncMock()

        await job.run(date(2025, 12, 20))

        mock_state_manager.mark_running.assert_not_called()

    @pytest.mark.asyncio
    async def test_marks_success_after_sync(self, mock_state_manager):
        """Marks sync as success after calendar sync completes."""
        mock_state_manager.is_synced.return_value = False
        mock_state_manager.mark_running = AsyncMock()
        mock_state_manager.mark_success = AsyncMock()

        job = CalendarSyncJob(mock_state_manager)
        job._do_sync_calendar = AsyncMock()
        job._check_calendar_exists = AsyncMock(return_value=False)

        await job.run(date(2025, 12, 20))

        mock_state_manager.mark_success.assert_called_once_with("calendar", "2026")

    @pytest.mark.asyncio
    async def test_marks_failed_after_sync_failure(self, mock_state_manager):
        """Marks sync as failed after all retries exhausted."""
        mock_state_manager.is_synced.return_value = False

        job = CalendarSyncJob(mock_state_manager)
        job._check_calendar_exists = AsyncMock(return_value=False)
        # Mock sync_with_retry to return False
        with patch("galaxy_core.application.scheduler.calendar_sync_job.sync_with_retry", return_value=False):
            await job.run(date(2025, 12, 20))

        mock_state_manager.mark_failed.assert_called_once_with(
            "calendar", "2026", "All retries exhausted"
        )

    @pytest.mark.asyncio
    async def test_december_31_checks_existence(self, mock_state_manager):
        """Dec 31 checks if next year calendar exists."""
        job = CalendarSyncJob(mock_state_manager)
        job._check_calendar_exists = AsyncMock(return_value=True)
        job._do_sync_calendar = AsyncMock()

        await job.run(date(2025, 12, 31))

        job._check_calendar_exists.assert_called_once_with(2026)


class TestDoSyncCalendarValidation:
    """Tests for _do_sync_calendar validation."""

    @pytest.mark.asyncio
    async def test_do_sync_calendar_validates_min_days(self, mock_state_manager):
        """_do_sync_calendar should raise ValueError when trading days < 200."""
        mock_calendar_service = MagicMock()
        mock_calendar_service.sync_calendar_async = AsyncMock(return_value=150)

        job = CalendarSyncJob(mock_state_manager, calendar_service=mock_calendar_service)

        with pytest.raises(ValueError, match="only 150 trading days"):
            await job._do_sync_calendar(2026)

    @pytest.mark.asyncio
    async def test_do_sync_calendar_accepts_valid_count(self, mock_state_manager):
        """_do_sync_calendar should not raise when trading days >= 200."""
        mock_calendar_service = MagicMock()
        mock_calendar_service.sync_calendar_async = AsyncMock(return_value=250)

        job = CalendarSyncJob(mock_state_manager, calendar_service=mock_calendar_service)

        # Should not raise
        await job._do_sync_calendar(2026)


class TestCheckCalendarExists:
    """Tests for _check_calendar_exists method."""

    @pytest.mark.asyncio
    async def test_check_calendar_exists_returns_false_on_exception(self, mock_state_manager):
        """_check_calendar_exists should return False when exception occurs."""
        mock_calendar_store = MagicMock()
        mock_calendar_store.get_trading_days = AsyncMock(side_effect=Exception("DB error"))

        job = CalendarSyncJob(mock_state_manager, calendar_store=mock_calendar_store)

        result = await job._check_calendar_exists(2026)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_calendar_exists_returns_true_when_enough_days(self, mock_state_manager):
        """_check_calendar_exists should return True when >= 200 trading days."""
        mock_calendar_store = MagicMock()
        # 250 mock trading days
        mock_calendar_store.get_trading_days = AsyncMock(
            return_value=[MagicMock() for _ in range(250)]
        )

        job = CalendarSyncJob(mock_state_manager, calendar_store=mock_calendar_store)

        result = await job._check_calendar_exists(2026)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_calendar_exists_returns_false_when_few_days(self, mock_state_manager):
        """_check_calendar_exists should return False when < 200 trading days."""
        mock_calendar_store = MagicMock()
        # 50 mock trading days
        mock_calendar_store.get_trading_days = AsyncMock(
            return_value=[MagicMock() for _ in range(50)]
        )

        job = CalendarSyncJob(mock_state_manager, calendar_store=mock_calendar_store)

        result = await job._check_calendar_exists(2026)

        assert result is False


class TestCurrentYearCompleteness:
    """Tests for non-December current-year completeness check (2026-07-14 fix).

    历史背景: 原 run() 非 12 月立即 return,导致当前年日历出现缺口时无自愈
    机制,_check_kline_trigger 查不到交易日 → K线同步静默哑火。修复后非 12 月
    每天校验当前年完整性。
    """

    @pytest.mark.asyncio
    async def test_non_december_skips_when_calendar_complete(self, mock_state_manager):
        """非 12 月且日历完整 → 不调 _sync_calendar。"""
        mock_calendar_store = MagicMock()
        # 7 月中旬阈值 = (7-1)×18 = 108;给 120 个交易日,完整。
        mock_calendar_store.get_trading_days = AsyncMock(
            return_value=[MagicMock() for _ in range(120)]
        )

        job = CalendarSyncJob(mock_state_manager, calendar_store=mock_calendar_store)
        job._sync_calendar = AsyncMock()

        await job.run(date(2026, 7, 14))

        job._sync_calendar.assert_not_called()
        mock_calendar_store.get_trading_days.assert_called_once_with(
            date(2026, 1, 1), date(2026, 7, 14)
        )

    @pytest.mark.asyncio
    async def test_non_december_syncs_when_calendar_has_gap(self, mock_state_manager):
        """非 12 月且交易日数低于阈值 → 调 _sync_calendar 补全年。"""
        mock_calendar_store = MagicMock()
        # 7 月中旬阈值 = 108;只给 5 个交易日(模拟本次 7/9 断档场景)。
        mock_calendar_store.get_trading_days = AsyncMock(
            return_value=[MagicMock() for _ in range(5)]
        )

        job = CalendarSyncJob(mock_state_manager, calendar_store=mock_calendar_store)
        job._sync_calendar = AsyncMock()

        await job.run(date(2026, 7, 14))

        job._sync_calendar.assert_called_once_with(2026, "calendar", "2026")

    @pytest.mark.asyncio
    async def test_january_uses_proportional_threshold(self, mock_state_manager):
        """1 月阈值 = (1-1)×18 = 0,任何非负交易日数都通过(不误判月初数据少)。"""
        mock_calendar_store = MagicMock()
        # 1 月初,数据天然少。阈值 0,给 3 个交易日也应通过(>= 0)。
        mock_calendar_store.get_trading_days = AsyncMock(
            return_value=[MagicMock() for _ in range(3)]
        )

        job = CalendarSyncJob(mock_state_manager, calendar_store=mock_calendar_store)
        job._sync_calendar = AsyncMock()

        await job.run(date(2026, 1, 5))

        job._sync_calendar.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_december_without_store_skips(self, mock_state_manager):
        """未注入 calendar_store 时(如旧测试)静默跳过,不报错。"""
        job = CalendarSyncJob(mock_state_manager)  # calendar_store=None
        job._sync_calendar = AsyncMock()

        # 不应抛异常
        await job.run(date(2026, 7, 14))

        job._sync_calendar.assert_not_called()

    @pytest.mark.asyncio
    async def test_december_still_uses_next_year_logic(self, mock_state_manager):
        """回归: 12 月仍走 next_year 逻辑,不走当前年校验。"""
        mock_calendar_store = MagicMock()
        mock_calendar_store.get_trading_days = AsyncMock(return_value=[])

        job = CalendarSyncJob(mock_state_manager, calendar_store=mock_calendar_store)
        job._check_calendar_exists = AsyncMock(return_value=False)
        job._do_sync_calendar = AsyncMock()
        mock_state_manager.is_synced.return_value = False

        await job.run(date(2025, 12, 25))

        # 12 月查的是 next_year(2026),不是当前年校验路径
        job._check_calendar_exists.assert_called_once_with(2026)
        # 当前年校验路径(get_trading_days 查 1/1~today)不应被调用
        mock_calendar_store.get_trading_days.assert_not_called()
