"""CalendarDataService 单元测试."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from galaxy_core.services.calendar_data_service import CalendarDataService


class TestCalendarDataServiceConstruction:
    """验证构造函数签名和端口依赖."""

    def test_constructor_accepts_port_dependencies(self):
        """CalendarDataService 构造函数应接收 2 个端口参数."""
        provider = MagicMock()
        store = MagicMock()

        service = CalendarDataService(
            calendar_provider=provider,
            calendar_store=store,
        )

        assert service._provider is provider
        assert service._store is store

    def test_service_has_sync_method(self):
        """CalendarDataService 应有 sync 方法."""
        service = CalendarDataService(
            calendar_provider=MagicMock(),
            calendar_store=MagicMock(),
        )

        assert hasattr(service, "sync")
        assert callable(service.sync)


class TestCalendarDataServiceSync:
    """验证 sync 方法行为."""

    @pytest.mark.asyncio
    async def test_sync_calls_provider_and_store(self):
        """sync 应调用 provider.get_trading_calendar 和 store.save_calendar."""
        provider = AsyncMock()
        store = AsyncMock()

        mock_dates = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
        provider.get_trading_calendar.return_value = mock_dates

        service = CalendarDataService(provider, store)
        result = await service.sync(year=2024)

        provider.get_trading_calendar.assert_called_once_with(2024)
        store.save_calendar.assert_called_once_with(mock_dates)
        assert result == 3

    @pytest.mark.asyncio
    async def test_sync_returns_zero_for_empty_calendar(self):
        """日历为空时应返回 0."""
        provider = AsyncMock()
        store = AsyncMock()

        provider.get_trading_calendar.return_value = []

        service = CalendarDataService(provider, store)
        result = await service.sync(year=2024)

        assert result == 0
        store.save_calendar.assert_not_called()
