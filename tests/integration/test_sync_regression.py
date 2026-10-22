"""SYNC-05 集成回归测试 — KlineDataService.sync() 端到端验证.

使用真实数据库连接验证：
- KlineStoreAdapter 真实读写
- last_sync_date 持久化
- 增量同步范围正确性

测试数据使用 TEST000.SH 等虚构 symbol 避免与生产数据冲突，
测试完成后 DELETE 清理。
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

from galaxy_core.database.services.adapters.calendar_store_adapter import CalendarStoreAdapter
from galaxy_core.database.services.adapters.kline_store_adapter import KlineStoreAdapter
from galaxy_core.domain.value_objects import Interval, KlineBar, SecurityType
from galaxy_core.services.kline_data_service import KlineDataService


@pytest.fixture
def mock_provider():
    """创建 mock KlineProviderPort."""
    provider = MagicMock()
    provider.get_kline = AsyncMock()
    provider.get_stock_list = AsyncMock(return_value=[])
    provider.get_listing_dates = AsyncMock(return_value={})
    return provider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bar(symbol: str, trade_time: datetime, **kwargs) -> KlineBar:
    """创建 KlineBar 实例（填充默认值）."""
    defaults = {
        "open": 10.0,
        "high": 11.0,
        "low": 9.0,
        "close": 10.5,
        "volume": 1000,
        "amount": 10000.0,
        "security_type": SecurityType.EXTRA_ETF,
    }
    defaults.update(kwargs)
    return KlineBar(symbol=symbol, trade_time=trade_time, **defaults)


async def _cleanup_test_data(db_manager, symbol: str) -> None:
    """清理测试数据 — 删除 kline_day 和 last_sync_date 中的测试记录."""
    async with db_manager.session() as session:
        await session.execute(
            text("DELETE FROM kline_day WHERE symbol = :symbol"),
            {"symbol": symbol},
        )
        await session.execute(
            text("DELETE FROM last_sync_date WHERE symbol = :symbol"),
            {"symbol": symbol},
        )


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSyncRegressionIntegration:
    """SYNC-05 集成回归测试 — 真实数据库端到端流程."""

    async def test_sync_day_interval_e2e(self, db_manager, mock_provider):
        """day 周期端到端：验证 DB 写入 + last_sync_date 记录."""
        test_symbol = "TEST000.SH"

        await _cleanup_test_data(db_manager, test_symbol)

        try:
            store = KlineStoreAdapter(db_manager)
            reference = mock_provider
            # mock 日历:只含 mock bars 的交易日,覆盖率 100% 绕开熔断(本测试验增量范围,不验熔断)
            calendar = AsyncMock()
            calendar.get_trading_days = AsyncMock(
                side_effect=lambda s, e: [
                    d
                    for d in [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
                    if s <= d <= e
                ]
            )

            # mock provider 返回模拟数据
            bars = [
                _make_bar(test_symbol, datetime(2024, 1, 2, 10, 0, 0)),
                _make_bar(test_symbol, datetime(2024, 1, 3, 10, 0, 0)),
                _make_bar(test_symbol, datetime(2024, 1, 4, 10, 0, 0)),
            ]
            mock_provider.get_kline = AsyncMock(return_value=bars)

            service = KlineDataService(mock_provider, store, reference, calendar)

            result = await service.sync(
                symbols=[test_symbol],
                interval=Interval.DAY,
                start="20240101",
                end="20240131",
            )

            # 验证结果
            assert result.success_count == 1
            assert result.synced_records == 3

            # 验证数据库写入
            async with db_manager.session() as session:
                rows_result = await session.execute(
                    text(
                        "SELECT COUNT(*) FROM kline_day WHERE symbol = :symbol"
                    ),
                    {"symbol": test_symbol},
                )
                count = rows_result.scalar()
                assert count == 3, f"kline_day 应有 3 条记录，实际 {count}"

            # 验证 last_sync_date 记录
            async with db_manager.session() as session:
                lsd_result = await session.execute(
                    text(
                        "SELECT last_sync_date FROM last_sync_date "
                        "WHERE symbol = :symbol AND interval = :interval"
                    ),
                    {"symbol": test_symbol, "interval": "day"},
                )
                row = lsd_result.fetchone()
                assert row is not None, "last_sync_date 应有记录"
                assert row[0] == date(2024, 1, 4), f"last_sync_date 应为 2024-01-04，实际 {row[0]}"

        finally:
            await _cleanup_test_data(db_manager, test_symbol)

    async def test_last_sync_date_persists(self, db_manager, mock_provider):
        """验证 last_sync_date 持久化：两次 sync 验证增量范围正确."""
        test_symbol = "TEST000.SH"

        await _cleanup_test_data(db_manager, test_symbol)

        try:
            store = KlineStoreAdapter(db_manager)
            reference = mock_provider
            calendar = AsyncMock()
            calendar.get_trading_days = AsyncMock(
                side_effect=lambda s, e: [
                    d
                    for d in [
                        date(2024, 1, 2),
                        date(2024, 1, 3),
                        date(2024, 1, 4),
                        date(2024, 1, 5),
                    ]
                    if s <= d <= e
                ]
            )

            # 第一次 sync：2024-01-02 到 2024-01-03
            first_bars = [
                _make_bar(test_symbol, datetime(2024, 1, 2, 10, 0, 0)),
                _make_bar(test_symbol, datetime(2024, 1, 3, 10, 0, 0)),
            ]
            mock_provider.get_kline = AsyncMock(return_value=first_bars)

            service = KlineDataService(mock_provider, store, reference, calendar)
            result1 = await service.sync(
                symbols=[test_symbol],
                interval=Interval.DAY,
                start="20240101",
                end="20240131",
            )

            assert result1.synced_records == 2

            # 验证 get_last_sync_dates 返回正确值
            last_dates = await store.get_last_sync_dates([test_symbol], Interval.DAY)
            assert last_dates.get(test_symbol) == date(2024, 1, 3)

            # 第二次 sync：mock 返回 2024-01-04 到 2024-01-05
            # 由于 last_sync_date=2024-01-03，查询范围应从 2024-01-04 开始
            second_bars = [
                _make_bar(test_symbol, datetime(2024, 1, 4, 10, 0, 0)),
                _make_bar(test_symbol, datetime(2024, 1, 5, 10, 0, 0)),
            ]
            mock_provider.get_kline = AsyncMock(return_value=second_bars)

            result2 = await service.sync(
                symbols=[test_symbol],
                interval=Interval.DAY,
                start="20240101",
                end="20240131",
            )

            assert result2.synced_records == 2

            # 验证第二次 sync 的 API 调用 start 为 20240104（last+1）
            call_kwargs = mock_provider.get_kline.call_args.kwargs
            assert call_kwargs["start"] == "20240104", (
                f"增量同步应从 20240104 开始，实际 {call_kwargs['start']}"
            )

            # 验证数据库总记录数
            async with db_manager.session() as session:
                rows_result = await session.execute(
                    text(
                        "SELECT COUNT(*) FROM kline_day WHERE symbol = :symbol"
                    ),
                    {"symbol": test_symbol},
                )
                count = rows_result.scalar()
                assert count == 4, f"kline_day 应有 4 条记录，实际 {count}"

            # 验证 last_sync_date 已更新到最新
            last_dates2 = await store.get_last_sync_dates([test_symbol], Interval.DAY)
            assert last_dates2.get(test_symbol) == date(2024, 1, 5)

        finally:
            await _cleanup_test_data(db_manager, test_symbol)
