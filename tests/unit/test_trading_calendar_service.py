"""交易日历服务单元测试模块.

测试 trading_calendar_service 的功能，包括：
- 缓存命中日志
- 异步方法（get_trading_days_async, get_previous_trading_day_async, sync_years）
"""

import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, AsyncMock


def _make_service():
    """创建带 mock db_manager 的 TradingCalendarService."""
    from galaxy_core.database.services.trading_calendar import (
        TradingCalendarService,
    )
    mock_db = MagicMock()
    return TradingCalendarService(db_manager=mock_db)


class TestTradingCalendarServiceAsync(unittest.TestCase):
    """交易日历服务异步方法测试类."""

    def test_get_trading_days_async_returns_trading_days_from_cache(self):
        """测试异步获取交易日列表：缓存完全覆盖时直接返回交易日."""
        async def run_test():
            mock_rows = [
                SimpleNamespace(trade_date=date(2024, 1, 2), is_trading_day=True),
                SimpleNamespace(trade_date=date(2024, 1, 3), is_trading_day=True),
                SimpleNamespace(trade_date=date(2024, 1, 4), is_trading_day=True),
                SimpleNamespace(trade_date=date(2024, 1, 5), is_trading_day=False),
                SimpleNamespace(trade_date=date(2024, 1, 6), is_trading_day=True),
                SimpleNamespace(trade_date=date(2024, 1, 7), is_trading_day=True),
            ]

            # 实际实现用 result.all() 而非 result.scalars().all()
            mock_result = MagicMock()
            mock_result.all.return_value = [
                (row.trade_date,) for row in mock_rows if row.is_trading_day
            ]

            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_session_context = MagicMock()
            mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_context.__aexit__ = AsyncMock(return_value=None)

            service = _make_service()
            service._db.session = MagicMock(return_value=mock_session_context)

            result = await service.get_trading_days_async(
                date(2024, 1, 2), date(2024, 1, 7),
            )
            return result

        import asyncio
        result = asyncio.run(run_test())
        # 仅返回 is_trading_day=True 的日期
        self.assertEqual(
            result,
            [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 6), date(2024, 1, 7)],
        )

    def test_get_previous_trading_day_async_returns_previous_day(self):
        """测试异步获取上一个交易日."""
        async def run_test():
            service = _make_service()

            with patch.object(
                service,
                "get_trading_days_async",
                new_callable=AsyncMock,
                return_value=[date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)],
            ):
                result = await service.get_previous_trading_day_async(
                    date(2024, 1, 5),
                )
                return result

        import asyncio
        result = asyncio.run(run_test())
        self.assertEqual(result, date(2024, 1, 4))

    def test_get_trading_days_async_converts_aware_datetime_to_date(self):
        """回归: ORM trade_date 是 timestamptz,SELECT 返 aware datetime,
        service 必须转成 date(对齐 calendar_store_adapter 模式)。
        见 AGENTS.md 2026-07-28 Bug 1: 2026-07-17 timestamptz 改造后漏转,
        导致 get_previous_trading_day_async `d < target_date` 比较
        datetime vs date 抛 TypeError。"""
        async def run_test():
            # 模拟 ORM 返 aware datetime(北京时区 2024-01-03 00:00 的 instant)
            aware_dates = [
                (datetime(2024, 1, 2, 16, 0, tzinfo=timezone.utc),),  # 北京 1/3 00:00
                (datetime(2024, 1, 3, 16, 0, tzinfo=timezone.utc),),
                (datetime(2024, 1, 4, 16, 0, tzinfo=timezone.utc),),
            ]
            mock_result = MagicMock()
            mock_result.all.return_value = aware_dates

            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_session_context = MagicMock()
            mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_context.__aexit__ = AsyncMock(return_value=None)

            service = _make_service()
            service._db.session = MagicMock(return_value=mock_session_context)

            result = await service.get_trading_days_async(
                date(2024, 1, 3), date(2024, 1, 5),
            )
            return result

        import asyncio
        result = asyncio.run(run_test())
        # 必须返 date 实例(非 datetime),且按北京 wall-clock 解释(UTC 16:00 → 北京次日)
        self.assertEqual(result, [date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 5)])
        for d in result:
            self.assertIsInstance(d, date)
            self.assertNotIsInstance(d, datetime)

    def test_get_previous_trading_day_async_handles_aware_datetime_from_db(self):
        """回归: get_trading_days_async 返 aware datetime 时,
        get_previous_trading_day_async `d < target_date` 不再抛 TypeError。
        见 AGENTS.md 2026-07-28: scheduler.run_week 7/21-7/28 连环 6 次 crash。

        注: 不直接 patch get_trading_days_async(否则绕过 _to_date 转换),
        而是让真实 SQL 查询路径返 aware datetime(模拟 ORM timestamptz 列读出)。"""
        async def run_test():
            aware_dates = [
                (datetime(2024, 1, 2, 16, 0, tzinfo=timezone.utc),),
                (datetime(2024, 1, 3, 16, 0, tzinfo=timezone.utc),),
                (datetime(2024, 1, 4, 16, 0, tzinfo=timezone.utc),),
            ]
            mock_result = MagicMock()
            mock_result.all.return_value = aware_dates

            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_session_context = MagicMock()
            mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_context.__aexit__ = AsyncMock(return_value=None)

            service = _make_service()
            service._db.session = MagicMock(return_value=mock_session_context)

            result = await service.get_previous_trading_day_async(
                date(2024, 1, 5),
            )
            return result

        import asyncio
        # 不再抛 TypeError,应返 date(2024, 1, 4)
        result = asyncio.run(run_test())
        self.assertEqual(result, date(2024, 1, 4))

    def test_sync_years_calls_sync_calendar_for_each_year(self):
        """测试异步同步多年交易日历：每年调用一次 sync_calendar_async."""
        async def run_test():
            service = _make_service()

            with patch.object(
                service,
                "sync_calendar_async",
                new_callable=AsyncMock,
                return_value=250,
            ) as mock_sync:
                stats = await service.sync_years(2023, 2024)
                return stats, mock_sync

        import asyncio
        stats, mock_sync = asyncio.run(run_test())
        self.assertEqual(mock_sync.call_count, 2)
        mock_sync.assert_any_call(2023)
        mock_sync.assert_any_call(2024)
        self.assertEqual(stats["total"], 500)
        self.assertEqual(stats["added"], 500)
        self.assertEqual(stats["skipped"], 0)


class TestSaveToDbInstantConsistency(unittest.TestCase):
    """_save_to_db_async 写入/删除的日期一致性(nocodb 形态,2026-08-26 回迁).

    trade_date 列已从 timestamptz 改为 date:写入/删除边界直接用 date 对象,
    不再需要 localize_cst 的 aware instant(历史 bug 语境见 git 历史 2026-07-29)。
    """

    def test_save_uses_date_for_trade_date(self):
        """insert 的 trade_date 必须是 date 对象(nocodb 形态 date 列)."""
        async def run_test():
            from galaxy_core.shared_kernel.utils.constants import localize_cst

            service = _make_service()
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value=None)
            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            service._db.session = MagicMock(return_value=mock_ctx)

            await service._save_to_db_async(
                trading_days=[date(2024, 1, 3)],
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 5),
            )

            # session.execute 调 2 次:delete + insert
            calls = mock_session.execute.call_args_list
            self.assertEqual(len(calls), 2)
            # insert 调用的 records 必须含 date 对象
            # (第 2 次调用是 insert,第 2 参数是 records list)
            insert_call = calls[1]
            # SQLAlchemy insert() 对象 + records,检查 records 内容
            # records 可能在 args[1] 或 kwargs
            self.assertEqual(insert_call.args[0].__class__.__name__, "Insert")
            # 第 2 个位置参数是 records list
            if len(insert_call.args) > 1:
                records = insert_call.args[1]
            else:
                # 某些版本走 kwargs
                records = list(insert_call.kwargs.values())[0]

            # 抽取 trade_date 值,验证是 date 对象
            trade_dates = [r["trade_date"] for r in records]
            self.assertIn(date(2024, 1, 3), trade_dates)
            for td in trade_dates:
                self.assertNotIsInstance(td, datetime)  # 必须是纯 date,非 datetime

        import asyncio
        asyncio.run(run_test())

    def test_save_delete_uses_date_bounds(self):
        """delete 的 >= / <= 边界直接用 date 对象(nocodb 形态 date 列)."""
        async def run_test():
            from galaxy_core.shared_kernel.utils.constants import localize_cst

            service = _make_service()
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value=None)
            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            service._db.session = MagicMock(return_value=mock_ctx)

            await service._save_to_db_async(
                trading_days=[date(2024, 1, 3)],
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 5),
            )

            # 第 1 次 execute 是 delete,WHERE 的边界应是 localize_cst 的 aware datetime
            delete_stmt = mock_session.execute.call_args_list[0].args[0]
            # 编译看 WHERE 子句的 bind params
            compiled = delete_stmt.compile()
            params = compiled.params
            # 边界值必须是 date 对象
            for v in params.values():
                self.assertNotIsInstance(v, datetime)
                self.assertIsInstance(v, date)
            bound_vals = list(params.values())
            self.assertIn(date(2024, 1, 1), bound_vals)
            self.assertIn(date(2024, 1, 5), bound_vals)

        import asyncio
        asyncio.run(run_test())


class TestCalendarStoreDelegation(unittest.TestCase):
    """calendar 双写路径合并回归(2026-07-29)。

    TradingCalendarService 注入 calendar_store 后,DB 操作应委托给 store,
    不再走自身的 _save_to_db_async 直接写 DB 路径(消除双写 instant 错位风险)。
    """

    def test_get_trading_days_delegates_to_store_when_injected(self):
        """注入 store 后,get_trading_days_async 委托 store.get_trading_days。"""
        async def run_test():
            from galaxy_core.database.services.trading_calendar import (
                TradingCalendarService,
            )
            mock_store = MagicMock()
            mock_store.get_trading_days = AsyncMock(
                return_value=[date(2024, 1, 3), date(2024, 1, 4)]
            )
            service = TradingCalendarService(
                db_manager=MagicMock(), calendar_store=mock_store
            )
            result = await service.get_trading_days_async(
                date(2024, 1, 1), date(2024, 1, 5)
            )
            mock_store.get_trading_days.assert_called_once_with(
                date(2024, 1, 1), date(2024, 1, 5)
            )
            assert result == [date(2024, 1, 3), date(2024, 1, 4)]

        import asyncio
        asyncio.run(run_test())

    def test_save_delegates_to_store_when_injected(self):
        """注入 store 后,_save_to_db_async 委托 store.save_calendar。"""
        async def run_test():
            from galaxy_core.database.services.trading_calendar import (
                TradingCalendarService,
            )
            mock_store = MagicMock()
            mock_store.save_calendar = AsyncMock(return_value=None)
            service = TradingCalendarService(
                db_manager=MagicMock(), calendar_store=mock_store
            )
            await service._save_to_db_async(
                trading_days=[date(2024, 1, 3)],
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 5),
            )
            # 委托 store.save_calendar(trading_days)
            mock_store.save_calendar.assert_called_once_with([date(2024, 1, 3)])

        import asyncio
        asyncio.run(run_test())

    def test_no_store_falls_back_to_direct_db(self):
        """无 store(向后兼容)时走自身 DB 路径(不抛错)。"""
        async def run_test():
            from galaxy_core.database.services.trading_calendar import (
                TradingCalendarService,
            )
            service = _make_service()  # 无 calendar_store
            # service._store 应为 None
            assert service._store is None
            # 不实际执行 DB(会因 mock 失败),只验证 _store=None 不抛

        import asyncio
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
