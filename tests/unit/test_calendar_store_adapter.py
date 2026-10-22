"""CalendarStoreAdapter 测试."""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from galaxy_core.database.services.adapters.calendar_store_adapter import CalendarStoreAdapter
from galaxy_core.domain.ports.calendar_store import CalendarStorePort


class TestCalendarStoreAdapterProtocol:
    """验证 CalendarStoreAdapter 满足 CalendarStorePort Protocol."""

    def test_adapter_is_protocol_instance(self):
        """CalendarStoreAdapter 应满足 CalendarStorePort Protocol."""
        mock_db = MagicMock()
        adapter = CalendarStoreAdapter(mock_db)
        assert isinstance(adapter, CalendarStorePort)

    def test_adapter_has_async_save_calendar(self):
        """save_calendar 应为 async 方法."""
        mock_db = MagicMock()
        adapter = CalendarStoreAdapter(mock_db)
        import inspect
        assert inspect.iscoroutinefunction(adapter.save_calendar)

    def test_adapter_has_async_get_trading_calendar(self):
        """get_trading_calendar 应为 async 方法."""
        mock_db = MagicMock()
        adapter = CalendarStoreAdapter(mock_db)
        import inspect
        assert inspect.iscoroutinefunction(adapter.get_trading_calendar)


class TestCalendarStoreAdapterSaveCalendar:
    """save_calendar 方法测试."""

    def test_saves_empty_list(self):
        """空列表应直接返回."""
        mock_db = MagicMock()
        adapter = CalendarStoreAdapter(mock_db)
        asyncio.run(adapter.save_calendar([]))

    def test_saves_trading_dates(self):
        """应保存交易日列表."""
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_db = MagicMock()
        mock_db.session.return_value = mock_session_ctx

        dates = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]

        adapter = CalendarStoreAdapter(mock_db)
        asyncio.run(adapter.save_calendar(dates))

        # 验证 session 被使用
        mock_db.session.assert_called_once()


class TestCalendarStoreAdapterGetTradingCalendar:
    """get_trading_calendar 方法测试."""

    def test_returns_trading_dates(self):
        """应返回交易日列表."""
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: date(2024, 1, 2)

        mock_result = MagicMock()
        mock_result.all.return_value = [(date(2024, 1, 2),), (date(2024, 1, 3),)]
        mock_session.execute.return_value = mock_result

        mock_db = MagicMock()
        mock_db.session.return_value = mock_session_ctx

        adapter = CalendarStoreAdapter(mock_db)
        result = asyncio.run(adapter.get_trading_calendar(2024))

        assert len(result) == 2
        assert all(isinstance(d, date) for d in result)
