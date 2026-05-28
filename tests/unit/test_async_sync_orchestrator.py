"""Async K-line orchestrator regression tests."""

from __future__ import annotations

import asyncio
import sys
import threading
import types
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

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

from galaxy_db_sync.application.kline.error import KlineError, KlineErrorCode
from galaxy_db_sync.application.kline.result import KlineItemResult, KlineQueryResult

BatchKey = tuple[int, int, int]
BatchResult = tuple[list[str], list[str], dict[str, pd.DataFrame]]


def _frame(index: list[str], close_values: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"close": close_values}, index=pd.to_datetime(index))


def test_threadpool_batch_merge_preserves_deduped_sorted_results() -> None:
    """测试 ThreadPoolExecutor 批量抓取会正确合并、去重并排序结果."""
    from galaxy_db_sync.application.kline import sync_orchestrator

    range_groups = {
        (20240105, 20240105, 10008): ["600000.SH"],
        (20240103, 20240104, 10008): ["600000.SH"],
    }
    first_df = _frame(["2024-01-05", "2024-01-03"], [15.0, 13.0])
    second_df = _frame(["2024-01-03", "2024-01-04"], [99.0, 14.0])

    def fake_fetch_single_batch(
        key: BatchKey,
        symbols: list[str],
        semaphore: threading.Semaphore | None = None,
    ) -> BatchResult:
        del symbols, semaphore
        payloads = {
            (20240105, 20240105, 10008): (["600000.SH"], [], {"600000.SH": first_df}),
            (20240103, 20240104, 10008): (["600000.SH"], [], {"600000.SH": second_df}),
        }
        return payloads[key]

    with patch.object(
        sync_orchestrator,
        "fetch_single_batch",
        side_effect=fake_fetch_single_batch,
        create=True,
    ):
        results, failed_codes = sync_orchestrator.batch_fetch_kline_data(
            range_groups,
            max_workers=2,
        )

    assert failed_codes == []
    assert list(results["600000.SH"].index.strftime("%Y-%m-%d")) == [
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
    ]
    assert results["600000.SH"].loc[pd.Timestamp("2024-01-03"), "close"] == 99.0
    assert not results["600000.SH"].index.duplicated(keep="last").any()


def test_threadpool_batch_exception_extends_failed_codes_for_entire_batch() -> None:
    """测试 ThreadPoolExecutor 任务异常会将整批 symbols 标记为失败."""
    from galaxy_db_sync.application.kline import sync_orchestrator

    range_groups = {
        (20240101, 20240102, 10008): ["000001.SZ", "600000.SH"],
        (20240103, 20240103, 10008): ["300001.SZ"],
    }
    success_df = _frame(["2024-01-03"], [31.0])

    def fake_fetch_single_batch(
        key: BatchKey,
        symbols: list[str],
        semaphore: threading.Semaphore | None = None,
    ) -> BatchResult:
        del symbols, semaphore
        if key == (20240101, 20240102, 10008):
            raise RuntimeError("boom")
        return (["300001.SZ"], [], {"300001.SZ": success_df})

    with patch.object(
        sync_orchestrator,
        "fetch_single_batch",
        side_effect=fake_fetch_single_batch,
        create=True,
    ):
        results, failed_codes = sync_orchestrator.batch_fetch_kline_data(
            range_groups,
            max_workers=2,
        )

    assert set(failed_codes) == {"000001.SZ", "600000.SH"}
    assert results == {"300001.SZ": success_df}


def test_threadpool_batch_respects_semaphore_limit() -> None:
    """测试 ThreadPoolExecutor + threading.Semaphore 正确限制并发."""
    from galaxy_db_sync.application.kline import sync_orchestrator

    range_groups = {
        (20240101, 20240101, 10008): ["000001.SZ"],
        (20240102, 20240102, 10008): ["000002.SZ"],
        (20240103, 20240103, 10008): ["000003.SZ"],
        (20240104, 20240104, 10008): ["000004.SZ"],
    }
    active_counter = {"value": 0}
    max_active_counter = {"value": 0}
    lock = threading.Lock()

    def fake_query_kline_with_results(
        code_list: list[str],
        begin_date: int,
        end_date: int,
        interval: int,
        begin_time: int | None = None,
        end_time: int | None = None,
    ) -> KlineQueryResult:
        del begin_date, end_date, interval, begin_time, end_time
        with lock:
            active_counter["value"] += 1
            max_active_counter["value"] = max(
                max_active_counter["value"],
                active_counter["value"],
            )
        # Simulate work
        import time
        time.sleep(0.02)
        with lock:
            active_counter["value"] -= 1
        return KlineQueryResult(
            results={
                code_list[0]: KlineItemResult.from_success(
                    code=code_list[0],
                    data=_frame(["2024-01-01"], [1.0]),
                    interval="day",
                )
            }
        )

    with patch.object(
        sync_orchestrator,
        "query_kline_with_results",
        side_effect=fake_query_kline_with_results,
        create=True,
    ):
        results, failed_codes = sync_orchestrator.batch_fetch_kline_data(
            range_groups,
            max_workers=2,
        )

    assert failed_codes == []
    assert set(results) == {"000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ"}
    # With max_workers=2, the ThreadPoolExecutor respects the limit
    # The semaphore inside fetch_single_batch limits concurrent SDK calls
    assert max_active_counter["value"] <= 2


def test_threadpool_batch_marks_unsuccessful_or_missing_items_as_failed_codes() -> None:
    """测试 fetch_single_batch 正确标记失败和缺失的 symbols."""
    from galaxy_db_sync.application.kline import sync_orchestrator

    error = KlineError(
        error_code=KlineErrorCode.NO_DATA_FOUND,
        message="no data",
        affected_codes=["000002.SZ"],
    )
    query_result = KlineQueryResult(
        results={
            "000001.SZ": KlineItemResult.from_success(
                code="000001.SZ",
                data=_frame(["2024-01-01"], [10.0]),
                interval="day",
            ),
            "000002.SZ": KlineItemResult.from_error(
                code="000002.SZ",
                error=error,
                interval="day",
            ),
        }
    )

    with patch.object(
        sync_orchestrator,
        "query_kline_with_results",
        return_value=query_result,
        create=True,
    ):
        (
            success_symbols,
            failed_symbols,
            data_dict,
        ) = sync_orchestrator.fetch_single_batch(
            (20240101, 20240101, 10008),
            ["000001.SZ", "000002.SZ", "000003.SZ"],
            threading.Semaphore(2),
        )

    assert success_symbols == ["000001.SZ"]
    assert failed_symbols == ["000002.SZ", "000003.SZ"]
    assert list(data_dict) == ["000001.SZ"]


def test_threadpool_batch_handles_empty_range_group_without_crashing() -> None:
    """测试空 range_groups 不会崩溃."""
    from galaxy_db_sync.application.kline import sync_orchestrator

    results, failed_codes = sync_orchestrator.batch_fetch_kline_data(
        {},
        max_workers=2,
    )

    assert results == {}
    assert failed_codes == []


@pytest.mark.asyncio
async def test_execute_kline_query_async_exists_and_callable() -> None:
    """测试 execute_kline_query_async 存在且可调用."""
    from galaxy_db_sync.application.kline.sync_orchestrator import (
        execute_kline_query_async,
    )
    from unittest.mock import AsyncMock

    # Verify function exists and is async
    assert asyncio.iscoroutinefunction(execute_kline_query_async)

    # Mock dependencies to test basic call
    # Updated for AsyncKlineService integration
    with (
        patch(
            "galaxy_db_sync.application.kline.sync_orchestrator.AsyncKlineService",
        ) as mock_service_class,
        patch(
            "galaxy_db_sync.application.kline.sync_orchestrator.kline_completeness_checker.check",
            return_value=types.SimpleNamespace(is_complete=True),
        ),
    ):
        mock_service = AsyncMock()
        mock_service.query_kline_from_db = AsyncMock(return_value={})
        mock_service.merge_db_and_api_data = lambda db_data, api_data: db_data
        mock_service_class.return_value = mock_service

        result = await execute_kline_query_async(
            symbol_list=["600000.SH"],
            interval="day",
            start_date="20240101",
            end_date="20240110",
            interval_value=10008,
        )
        assert result == {}


@pytest.mark.asyncio
async def test_execute_kline_query_async_wraps_threadpool_with_to_thread() -> None:
    """测试 execute_kline_query_async 使用 asyncio.to_thread 包装 ThreadPoolExecutor."""
    from galaxy_db_sync.application.kline.sync_orchestrator import (
        execute_kline_query_async,
    )
    from galaxy_db_sync.database.services.kline_completeness_checker import (
        CompletenessResult,
    )
    from unittest.mock import AsyncMock

    api_df = _frame(["2024-01-05"], [12.0])

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
                    missing_ranges=[
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
                "galaxy_db_sync.application.kline.sync_orchestrator.batch_fetch_kline_data",
                return_value=(api_df.to_dict(), []),
            ) as mock_batch_fetch,
        ):
            mock_service = AsyncMock()
            mock_service.query_kline_from_db = AsyncMock(return_value={})
            mock_service.merge_db_and_api_data = lambda db_data, api_data: api_data
            mock_service_class.return_value = mock_service

            _ = await execute_kline_query_async(
                symbol_list=["600000.SH"],
                interval="day",
                start_date="20240101",
                end_date="20240110",
                interval_value=10008,
            )

            # Verify batch_fetch_kline_data was called (via asyncio.to_thread)
            mock_batch_fetch.assert_called_once()

    await run_test()


def test_query_kline_with_results_calls_sync_sdk_directly() -> None:
    """测试 query_kline_with_results 直接调用同步 SDK."""
    from galaxy_db_sync.application.kline import sync_orchestrator

    mock_kline_dict = {"600000.SH": _frame(["2024-01-01"], [10.0])}

    with patch.object(
        sync_orchestrator.amazing_data_client,
        "query_kline",
        return_value=mock_kline_dict,
        create=True,
    ) as mock_query_kline:
        result = sync_orchestrator.query_kline_with_results(
            code_list=["600000.SH"],
            begin_date=20240101,
            end_date=20240101,
            interval=10008,
        )

        mock_query_kline.assert_called_once_with(
            code_list=["600000.SH"],
            begin_date=20240101,
            end_date=20240101,
            interval=10008,
            begin_time=None,
            end_time=None,
        )
        assert "600000.SH" in result.results
        assert result.results["600000.SH"].success


@pytest.mark.asyncio
async def test_query_kline_with_results_async_wraps_sync() -> None:
    """测试 query_kline_with_results_async 包装同步实现."""
    from galaxy_db_sync.application.kline import sync_orchestrator

    with patch.object(
        sync_orchestrator,
        "query_kline_with_results",
        return_value=KlineQueryResult(
            results={
                "600000.SH": KlineItemResult.from_success(
                    code="600000.SH",
                    data=_frame(["2024-01-01"], [10.0]),
                    interval="day",
                )
            }
        ),
        create=True,
    ) as mock_sync:
        result = await sync_orchestrator.query_kline_with_results_async(
            code_list=["600000.SH"],
            begin_date=20240101,
            end_date=20240101,
            interval=10008,
        )

        mock_sync.assert_called_once()
        assert "600000.SH" in result.results
