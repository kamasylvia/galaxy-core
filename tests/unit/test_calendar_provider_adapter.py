"""CalendarProviderAdapter 测试."""

import asyncio
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from galaxy_core.amazing_data.api.adapters.calendar_provider_adapter import CalendarProviderAdapter
from galaxy_core.domain.ports.calendar_provider import CalendarProviderPort


class TestCalendarProviderAdapterProtocol:
    """验证 CalendarProviderAdapter 满足 CalendarProviderPort Protocol."""

    def test_adapter_is_protocol_instance(self):
        """CalendarProviderAdapter 应满足 CalendarProviderPort Protocol."""
        mock_client = MagicMock()
        adapter = CalendarProviderAdapter(mock_client)
        assert isinstance(adapter, CalendarProviderPort)

    def test_adapter_has_async_get_trading_calendar(self):
        """get_trading_calendar 应为 async 方法."""
        mock_client = MagicMock()
        adapter = CalendarProviderAdapter(mock_client)
        import inspect
        assert inspect.iscoroutinefunction(adapter.get_trading_calendar)


class TestCalendarProviderAdapterGetTradingCalendar:
    """get_trading_calendar 方法测试."""

    def test_returns_filtered_dates(self):
        """应返回指定年份的交易日列表."""
        mock_client = MagicMock()
        # SDK 返回 list[datetime]
        mock_client.get_trading_calendar.return_value = [
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
            datetime(2023, 12, 29),
            datetime(2024, 1, 4),
        ]

        adapter = CalendarProviderAdapter(mock_client)
        result = asyncio.run(adapter.get_trading_calendar(2024))

        assert len(result) == 3
        assert all(isinstance(d, date) for d in result)
        assert all(d.year == 2024 for d in result)

    def test_handles_int_format(self):
        """应处理 int 格式的日历数据."""
        mock_client = MagicMock()
        # SDK 返回 list[int] (YYYYMMDD 格式)
        mock_client.get_trading_calendar.return_value = [20240102, 20240103, 20231229]

        adapter = CalendarProviderAdapter(mock_client)
        result = asyncio.run(adapter.get_trading_calendar(2024))

        assert len(result) == 2
        assert all(d.year == 2024 for d in result)

    def test_handles_empty_calendar(self):
        """空日历应返回空列表."""
        mock_client = MagicMock()
        mock_client.get_trading_calendar.return_value = []

        adapter = CalendarProviderAdapter(mock_client)
        result = asyncio.run(adapter.get_trading_calendar(2024))
        assert result == []

    def test_calls_to_thread(self):
        """应使用 asyncio.to_thread 包装 SDK 调用."""
        mock_client = MagicMock()
        mock_client.get_trading_calendar.return_value = []

        adapter = CalendarProviderAdapter(mock_client)

        async def run():
            with patch("galaxy_core.amazing_data.api.adapters.calendar_provider_adapter.asyncio.to_thread") as mock_to_thread:
                mock_to_thread.return_value = []
                await adapter.get_trading_calendar(2024)
                mock_to_thread.assert_called_once()

        asyncio.run(run())
