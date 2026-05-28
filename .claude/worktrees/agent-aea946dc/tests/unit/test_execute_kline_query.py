"""K 线查询执行测试模块.

测试 execute_kline_query / execute_kline_query_async，包括：
- 多缺失区间合并
- 空查询缓存集成
- sync wrapper 通过 asyncio.run 委托 async 实现
- 并发数环境变量兼容
"""

import sys
import types
import unittest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch, sentinel

import pandas as pd

if "AmazingData" not in sys.modules:
    sys.modules["AmazingData"] = types.SimpleNamespace(
        login=lambda **kwargs: None,
        logout=lambda *args, **kwargs: None,
        BaseData=lambda: types.SimpleNamespace(get_calendar=lambda *args, **kwargs: []),
        InfoData=lambda: types.SimpleNamespace(),
        MarketData=lambda calendar: types.SimpleNamespace(query_kline=lambda **kwargs: {}),
    )

if "akshare" not in sys.modules:
    sys.modules["akshare"] = types.SimpleNamespace()

if "tgw" not in sys.modules:
    sys.modules["tgw"] = types.SimpleNamespace()

from galaxy_db_sync.database.services.kline_completeness_checker import (
    CompletenessResult,
)


class TestExecuteKlineQuery(unittest.TestCase):
    """execute_kline_query 函数测试类."""

    def test_execute_kline_query_async_merges_multiple_missing_ranges_for_same_symbol(self):
        """测试 execute_kline_query_async 会合并同一代码多个缺失区间的 API 结果."""
        from galaxy_db_sync.application.kline.sync_orchestrator import (
            execute_kline_query_async,
        )

        db_df = pd.DataFrame(
            {"close": [10.0]},
            index=pd.to_datetime(["2024-01-02"]),
        )

        api_df_first = pd.DataFrame(
            {"close": [11.0]},
            index=pd.to_datetime(["2024-01-03"]),
        )
        api_df_second = pd.DataFrame(
            {"close": [12.0]},
            index=pd.to_datetime(["2024-01-05"]),
        )

        async def run_test() -> None:
            with (
                # Updated for AsyncKlineService integration
                patch(
                    "galaxy_db_sync.application.kline.sync_orchestrator.AsyncKlineService",
                ) as mock_service_class,
                patch(
                    "galaxy_db_sync.application.kline.sync_orchestrator.kline_completeness_checker.check",
                    return_value=CompletenessResult(
                        is_complete=False,
                        missing_count=2,
                        total_count=3,
                        coverage_ratio=1 / 3,
                        missing_ranges=[
                            (
                                pd.Timestamp("2024-01-03").date(),
                                pd.Timestamp("2024-01-03").date(),
                            ),
                            (
                                pd.Timestamp("2024-01-05").date(),
                                pd.Timestamp("2024-01-05").date(),
                            ),
                        ],
                        check_method="short_period_trading_day",
                    ),
                ),
                patch(
                    "galaxy_db_sync.application.kline.sync_orchestrator.empty_query_service.is_confirmed_empty",
                    return_value=False,
                ),
                patch(
                    "galaxy_db_sync.application.kline.sync_orchestrator.batch_fetch_kline_data"
                ) as mock_batch_fetch,
            ):
                mock_service = AsyncMock()
                mock_service.query_kline_from_db = AsyncMock(return_value={"600000.SH": db_df})
                mock_service.merge_db_and_api_data = lambda db_data, api_data: api_data
                mock_service_class.return_value = mock_service

                mock_batch_fetch.return_value = (
                    {"600000.SH": pd.concat([api_df_first, api_df_second])},
                    [],
                )

                result = await execute_kline_query_async(
                    symbol_list=["600000.SH"],
                    interval="day",
                    start_date="20240101",
                    end_date="20240110",
                    interval_value=10008,
                )

                self.assertIn("600000.SH", result)
                self.assertEqual(len(result["600000.SH"]), 2)
                self.assertListEqual(
                    [ts.strftime("%Y-%m-%d") for ts in result["600000.SH"].index],
                    ["2024-01-03", "2024-01-05"],
                )
                mock_batch_fetch.assert_called_once_with(
                    {
                        (20240103, 20240103, 10008): ["600000.SH"],
                        (20240105, 20240105, 10008): ["600000.SH"],
                    },
                    max_workers=5,
                )

        import asyncio

        asyncio.run(run_test())

    def test_execute_kline_query_async_skips_confirmed_empty_ranges(self):
        """测试兼容查询路径会跳过已确认为空的缺失区间."""
        from galaxy_db_sync.application.kline.sync_orchestrator import (
            execute_kline_query_async,
        )

        db_df = pd.DataFrame(
            {"close": [10.0]},
            index=pd.to_datetime(["2024-01-02"]),
        )
        api_df = pd.DataFrame(
            {"close": [12.0]},
            index=pd.to_datetime(["2024-01-05"]),
        )

        async def run_test() -> None:
            with (
                # Updated for AsyncKlineService integration
                patch(
                    "galaxy_db_sync.application.kline.sync_orchestrator.AsyncKlineService",
                ) as mock_service_class,
                patch(
                    "galaxy_db_sync.application.kline.sync_orchestrator.kline_completeness_checker.check",
                    return_value=CompletenessResult(
                        is_complete=False,
                        missing_count=2,
                        total_count=3,
                        coverage_ratio=1 / 3,
                        missing_ranges=[
                            (date(2024, 1, 3), date(2024, 1, 3)),
                            (date(2024, 1, 5), date(2024, 1, 5)),
                        ],
                        check_method="short_period_trading_day",
                    ),
                ),
                patch(
                    "galaxy_db_sync.database.services.empty_query.empty_query_service.is_confirmed_empty",
                    side_effect=[True, False],
                ) as mock_is_confirmed_empty,
                patch(
                    "galaxy_db_sync.application.kline.sync_orchestrator.batch_fetch_kline_data"
                ) as mock_batch_fetch,
            ):
                mock_service = AsyncMock()
                mock_service.query_kline_from_db = AsyncMock(return_value={"600000.SH": db_df})
                mock_service.merge_db_and_api_data = lambda db_data, api_data: api_data
                mock_service_class.return_value = mock_service

                mock_batch_fetch.return_value = ({"600000.SH": api_df}, [])

                result = await execute_kline_query_async(
                    symbol_list=["600000.SH"],
                    interval="day",
                    start_date="20240101",
                    end_date="20240110",
                    interval_value=10008,
                )

                self.assertIn("600000.SH", result)
                self.assertEqual(len(result["600000.SH"]), 1)
                self.assertListEqual(
                    [ts.strftime("%Y-%m-%d") for ts in result["600000.SH"].index],
                    ["2024-01-05"],
                )
                self.assertEqual(mock_is_confirmed_empty.call_count, 2)
                mock_batch_fetch.assert_called_once_with(
                    {(20240105, 20240105, 10008): ["600000.SH"]},
                    max_workers=5,
                )

        import asyncio

        asyncio.run(run_test())

    def test_execute_kline_query_delegates_to_asyncio_run(self):
        """测试 execute_kline_query 通过 asyncio.run 委托 execute_kline_query_async."""
        from galaxy_db_sync.application.kline import sync_orchestrator

        with (
            patch.object(
                sync_orchestrator,
                "execute_kline_query_async",
                new=MagicMock(return_value=sentinel.coroutine),
            ) as mock_async,
            patch.object(sync_orchestrator.asyncio, "run", return_value={"ok": True}) as mock_run,
        ):
            result = sync_orchestrator.execute_kline_query(
                symbol_list=["600000.SH"],
                interval="day",
                start_date="20240101",
                end_date="20240110",
                interval_value=10008,
            )

        self.assertEqual(result, {"ok": True})
        mock_async.assert_called_once_with(
            symbol_list=["600000.SH"],
            interval="day",
            start_date="20240101",
            end_date="20240110",
            interval_value=10008,
            max_concurrent=None,
        )
        mock_run.assert_called_once_with(sentinel.coroutine)

    def test_execute_kline_query_async_uses_env_concurrency_when_omitted(self):
        """测试未显式传入 max_concurrent 时继续读取环境变量。"""
        from galaxy_db_sync.application.kline.sync_orchestrator import (
            execute_kline_query_async,
        )

        async def run_test() -> None:
            with (
                # Updated for AsyncKlineService integration
                patch(
                    "galaxy_db_sync.application.kline.sync_orchestrator.AsyncKlineService",
                ) as mock_service_class,
                patch(
                    "galaxy_db_sync.application.kline.sync_orchestrator.kline_completeness_checker.check",
                    return_value=CompletenessResult(
                        is_complete=False,
                        missing_count=1,
                        total_count=2,
                        coverage_ratio=0.5,
                        missing_ranges=[(date(2024, 1, 5), date(2024, 1, 5))],
                        check_method="short_period_trading_day",
                    ),
                ),
                patch(
                    "galaxy_db_sync.application.kline.sync_orchestrator.batch_fetch_kline_data",
                    return_value=({}, []),
                ) as mock_batch_fetch,
                patch(
                    "galaxy_db_sync.application.kline.sync_orchestrator.empty_query_service.is_confirmed_empty",
                    return_value=False,
                ),
                patch.dict(
                    "galaxy_db_sync.application.kline.sync_orchestrator.os.environ",
                    {"GALAXY_KLINE_MAX_CONCURRENT": "7"},
                    clear=False,
                ),
            ):
                mock_service = AsyncMock()
                mock_service.query_kline_from_db = AsyncMock(return_value={"600000.SH": pd.DataFrame()})
                mock_service.merge_db_and_api_data = lambda db_data, api_data: {}
                mock_service_class.return_value = mock_service

                await execute_kline_query_async(
                    symbol_list=["600000.SH"],
                    interval="day",
                    start_date="20240101",
                    end_date="20240110",
                    interval_value=10008,
                )

                mock_batch_fetch.assert_called_once_with(
                    {(20240105, 20240105, 10008): ["600000.SH"]},
                    max_workers=7,
                )

        import asyncio

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
