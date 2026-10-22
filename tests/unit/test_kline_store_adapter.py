"""KlineStoreAdapter 测试."""

import asyncio
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from galaxy_core.database.services.adapters.kline_store_adapter import KlineStoreAdapter
from galaxy_core.domain.ports.kline_store import KlineStorePort
from galaxy_core.domain.value_objects import Interval, KlineBar, SecurityType


class TestKlineStoreAdapterProtocol:
    """验证 KlineStoreAdapter 满足 KlineStorePort Protocol."""

    def test_adapter_is_protocol_instance(self):
        """KlineStoreAdapter 应满足 KlineStorePort Protocol."""
        mock_db = MagicMock()
        adapter = KlineStoreAdapter(mock_db)
        assert isinstance(adapter, KlineStorePort)

    def test_adapter_has_async_save_kline(self):
        """save_kline 应为 async 方法."""
        mock_db = MagicMock()
        adapter = KlineStoreAdapter(mock_db)
        import inspect
        assert inspect.iscoroutinefunction(adapter.save_kline)

    def test_adapter_has_async_get_kline(self):
        """get_kline 应为 async 方法."""
        mock_db = MagicMock()
        adapter = KlineStoreAdapter(mock_db)
        import inspect
        assert inspect.iscoroutinefunction(adapter.get_kline)

    def test_adapter_has_async_get_last_sync_dates(self):
        """get_last_sync_dates 应为 async 方法."""
        mock_db = MagicMock()
        adapter = KlineStoreAdapter(mock_db)
        import inspect
        assert inspect.iscoroutinefunction(adapter.get_last_sync_dates)

    def test_adapter_has_async_set_last_sync_dates(self):
        """set_last_sync_dates 应为 async 方法."""
        mock_db = MagicMock()
        adapter = KlineStoreAdapter(mock_db)
        import inspect
        assert inspect.iscoroutinefunction(adapter.set_last_sync_dates)


class TestKlineStoreAdapterSaveKline:
    """save_kline 方法测试."""

    def test_saves_empty_list(self):
        """空列表应直接返回."""
        mock_db = MagicMock()
        adapter = KlineStoreAdapter(mock_db)
        # 不应抛出异常
        asyncio.run(adapter.save_kline([], Interval.DAY))

    def test_saves_kline_bars(self):
        """应保存 KlineBar 列表."""
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_db = MagicMock()
        mock_db.session.return_value = mock_session_ctx

        bars = [
            KlineBar(
                symbol="600000.SH",
                trade_time=datetime(2024, 1, 2),
                open=10.0,
                high=11.0,
                low=9.5,
                close=10.5,
                volume=1000,
                amount=10500.0,
                security_type=SecurityType.EXTRA_STOCK_A,
            )
        ]

        adapter = KlineStoreAdapter(mock_db)
        asyncio.run(adapter.save_kline(bars, Interval.DAY))

        # 验证 session 被使用
        mock_db.session.assert_called_once()
        mock_session.execute.assert_called()


class TestKlineStoreAdapterGetKline:
    """get_kline 方法测试."""

    def test_returns_kline_bars(self):
        """应返回 KlineBar 列表."""
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        # 模拟数据库返回
        mock_row = MagicMock()
        mock_row.symbol = "600000.SH"
        mock_row.trade_time = datetime(2024, 1, 2)
        mock_row.open = 10.0
        mock_row.high = 11.0
        mock_row.low = 9.5
        mock_row.close = 10.5
        mock_row.volume = 1000
        mock_row.amount = 10500.0
        mock_row.security_type = "EXTRA_STOCK_A"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        mock_db = MagicMock()
        mock_db.session.return_value = mock_session_ctx

        adapter = KlineStoreAdapter(mock_db)
        result = asyncio.run(
            adapter.get_kline("600000.SH", Interval.DAY, "20240101", "20240131")
        )

        assert len(result) == 1
        assert isinstance(result[0], KlineBar)
        assert result[0].symbol == "600000.SH"


class TestKlineStoreAdapterLastSyncDate:
    """get_last_sync_dates / set_last_sync_dates 方法测试."""

    def test_get_last_sync_dates_returns_dict(self):
        """应返回 symbol -> last_sync_date 映射."""
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        # 模拟 LastSyncDate 行
        mock_row1 = MagicMock()
        mock_row1.symbol = "600000.SH"
        mock_row1.last_sync_date = date(2024, 1, 15)

        mock_row2 = MagicMock()
        mock_row2.symbol = "000001.SZ"
        mock_row2.last_sync_date = date(2024, 1, 10)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_row1, mock_row2]
        mock_session.execute.return_value = mock_result

        mock_db = MagicMock()
        mock_db.session.return_value = mock_session_ctx

        adapter = KlineStoreAdapter(mock_db)
        result = asyncio.run(
            adapter.get_last_sync_dates(
                ["600000.SH", "000001.SZ"], Interval.DAY
            )
        )

        assert result == {
            "600000.SH": date(2024, 1, 15),
            "000001.SZ": date(2024, 1, 10),
        }

    def test_get_last_sync_dates_empty_symbols(self):
        """空 symbol 列表应直接返回空 dict，不查询数据库."""
        mock_db = MagicMock()
        adapter = KlineStoreAdapter(mock_db)
        result = asyncio.run(adapter.get_last_sync_dates([], Interval.DAY))

        assert result == {}
        mock_db.session.assert_not_called()

    def test_set_last_sync_dates_upserts(self):
        """应通过 UPSERT 写入 last_sync_date 记录."""
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_db = MagicMock()
        mock_db.session.return_value = mock_session_ctx

        adapter = KlineStoreAdapter(mock_db)
        asyncio.run(
            adapter.set_last_sync_dates(
                {"600000.SH": date(2024, 1, 15)}, Interval.DAY
            )
        )

        mock_db.session.assert_called_once()
        mock_session.execute.assert_called_once()

    def test_set_last_sync_dates_empty_dict(self):
        """空 dict 应直接返回，不操作数据库."""
        mock_db = MagicMock()
        adapter = KlineStoreAdapter(mock_db)
        asyncio.run(adapter.set_last_sync_dates({}, Interval.DAY))

        mock_db.session.assert_not_called()
