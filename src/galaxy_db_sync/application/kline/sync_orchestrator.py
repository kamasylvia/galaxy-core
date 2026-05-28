"""K 线同步编排模块."""

import asyncio
import logging
import os
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, cast

import pandas as pd

from galaxy_db_sync.amazing_data.api.client import amazing_data_client
from galaxy_db_sync.database.core.async_connection import AsyncDatabaseManager
from galaxy_db_sync.database.services.kline import KlineService
from galaxy_db_sync.database.services.empty_query import empty_query_service
from galaxy_db_sync.database.services.kline_completeness_checker import (
    CompletenessResult,
    kline_completeness_checker,
)
from galaxy_db_sync.shared_kernel.utils.config_loader import get_config

from .error import KlineError, KlineErrorCode
from .result import KlineItemResult, KlineQueryResult, KlineSyncResult

logger = logging.getLogger(__name__)


def sync_kline_data(
    completeness_results: dict[str, Any],
    interval: str,
    full_start: str,
    full_end: str,
) -> KlineSyncResult:
    """同步 K 线数据 - 使用批量模式.

    Args:
        completeness_results: 每个 symbol 对应的完整性检查结果
        interval: K 线周期
        full_start: 补全后的开始日期（8 位 YYYYMMDD）
        full_end: 补全后的结束日期（8 位 YYYYMMDD）

    Returns:
        KlineSyncResult: 同步结果
    """
    from galaxy_db_sync.database.services.kline_data_sync import (
        kline_data_sync_service,
    )

    symbols_to_sync = [
        symbol for symbol, result in completeness_results.items() if not result.is_complete
    ]

    if not symbols_to_sync:
        logger.info("所有证券数据已完整，无需同步")
        return KlineSyncResult(
            success_count=len(completeness_results),
            synced_records=0,
            failed_codes=[],
            message="所有证券数据已完整，无需同步",
        )

    logger.info(f"开始批量同步 {len(symbols_to_sync)} 个证券的 K 线数据...")

    batch_result = kline_data_sync_service.batch_sync_kline_data(
        symbols=symbols_to_sync,
        interval=interval,
        start_date=full_start,
        end_date=full_end,
        completeness_results=completeness_results,
        batch_size=500,
    )

    complete_count = sum(1 for result in completeness_results.values() if result.is_complete)
    total_success = complete_count + batch_result.success_count

    # 注意：SDK 的 logout() 会调用 C 层 exit() 导致整个进程直接终止，
    # 因此跳过登出操作，由进程退出时自动清理连接。
    # username = get_config("amazing_data", "username")
    # amazing_data_client.logout(username)

    total = batch_result.total_symbols
    data = batch_result.api_data_count
    empty = batch_result.api_empty_count
    skipped = batch_result.skipped_by_cache_count
    failed = batch_result.failed_count

    logger.info(
        f"同步完成！需同步 {total} = 成功{data} + 空{empty} + 跳过{skipped} + 失败{failed}"
        f"（{batch_result.synced_records} 条记录）"
    )
    if failed > 0:
        logger.warning(f"同步失败的代码: {batch_result.failed_codes[:20]}...")

    return KlineSyncResult(
        success_count=total_success,
        synced_records=batch_result.synced_records,
        failed_codes=batch_result.failed_codes,
        message=(
            f"同步完成！需同步 {total} = 成功{data} + 空{empty} + 跳过{skipped} + 失败{failed}"
            f"（{batch_result.synced_records} 条记录）"
        ),
    )


async def sync_kline_data_async_impl(
    completeness_results: dict[str, Any],
    interval: str,
    full_start: str,
    full_end: str,
) -> KlineSyncResult:
    """异步同步 K 线数据 - 使用批量模式.

    Args:
        completeness_results: 每个 symbol 对应的完整性检查结果
        interval: K 线周期
        full_start: 补全后的开始日期（8 位 YYYYMMDD）
        full_end: 补全后的结束日期（8 位 YYYYMMDD）

    Returns:
        KlineSyncResult: 同步结果
    """
    from galaxy_db_sync.database.services.kline_data_sync import (
        kline_data_sync_service,
    )

    symbols_to_sync = [
        symbol for symbol, result in completeness_results.items() if not result.is_complete
    ]

    if not symbols_to_sync:
        logger.info("所有证券数据已完整，无需同步")
        return KlineSyncResult(
            success_count=len(completeness_results),
            synced_records=0,
            failed_codes=[],
            message="所有证券数据已完整，无需同步",
        )

    logger.info(f"开始批量同步 {len(symbols_to_sync)} 个证券的 K 线数据...")

    batch_result = await kline_data_sync_service.batch_sync_kline_data_async(
        symbols=symbols_to_sync,
        interval=interval,
        start_date=full_start,
        end_date=full_end,
        completeness_results=completeness_results,
        batch_size=500,
    )
    complete_count = sum(1 for result in completeness_results.values() if result.is_complete)
    total_success = complete_count + batch_result.success_count

    # 注意：SDK 的 logout() 会调用 C 层 exit() 导致整个进程直接终止，
    # 因此跳过登出操作，由进程退出时自动清理连接。

    total = batch_result.total_symbols
    data = batch_result.api_data_count
    empty = batch_result.api_empty_count
    skipped = batch_result.skipped_by_cache_count
    failed = batch_result.failed_count

    logger.info(
        f"同步完成！需同步 {total} = 成功{data} + 空{empty} + 跳过{skipped} + 失败{failed}"
        f"（{batch_result.synced_records} 条记录）"
    )
    if failed > 0:
        logger.warning(f"同步失败的代码: {batch_result.failed_codes[:20]}...")

    return KlineSyncResult(
        success_count=total_success,
        synced_records=batch_result.synced_records,
        failed_codes=batch_result.failed_codes,
        message=(
            f"同步完成！需同步 {total} = 成功{data} + 空{empty} + 跳过{skipped} + 失败{failed}"
            f"（{batch_result.synced_records} 条记录）"
        ),
    )


def group_symbols_by_missing_ranges(
    completeness_results: dict[str, CompletenessResult],
    interval: str,
) -> dict[tuple[int, int, str], list[str]]:
    """按缺失区间对 symbol 进行分组.

    Args:
        completeness_results: 每个 symbol 的完整性检查结果
        interval: K线周期 (如 "day", "min1")

    Returns:
        dict: key 为 (begin_date, end_date, interval), value 为 symbol 列表
    """
    range_groups: defaultdict[tuple[int, int, str], list[str]] = defaultdict(list)

    for symbol, result in completeness_results.items():
        if result.is_complete:
            continue

        for range_start, range_end in result.missing_ranges:
            if empty_query_service.is_confirmed_empty(
                symbol, interval, range_start, range_end
            ):
                continue

            begin_int = int(range_start.strftime("%Y%m%d"))
            end_int = int(range_end.strftime("%Y%m%d"))
            key = (begin_int, end_int, interval)
            range_groups[key].append(symbol)

    return dict(range_groups)


def fetch_single_batch(
    key: tuple[int, int, str],
    symbols: list[str],
    semaphore: threading.Semaphore | None = None,
) -> tuple[list[str], list[str], dict[str, pd.DataFrame]]:
    """获取一批 K 线数据（同步实现，直接调用 SDK）。"""
    begin_date, end_date, interval = key
    actual_semaphore = semaphore if semaphore is not None else threading.Semaphore(1)

    with actual_semaphore:
        query_result = query_kline_with_results(
            code_list=symbols,
            begin_date=begin_date,
            end_date=end_date,
            interval=interval,
        )

    success_symbols: list[str] = []
    failed_symbols: list[str] = []
    data_dict: dict[str, pd.DataFrame] = {}

    for symbol in symbols:
        if symbol in query_result.results:
            item_result = query_result.results[symbol]
            if item_result.success and item_result.data is not None:
                data_dict[symbol] = item_result.data
                success_symbols.append(symbol)
            else:
                failed_symbols.append(symbol)
        else:
            failed_symbols.append(symbol)

    return success_symbols, failed_symbols, data_dict


def batch_fetch_kline_data(
    range_groups: dict[tuple[int, int, str], list[str]],
    max_workers: int = 1,  # API 不支持并发，强制串行
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """串行批量获取 K 线数据（API 不支持并发）。"""
    results: dict[str, pd.DataFrame] = {}
    failed_codes: list[str] = []

    if not range_groups:
        return results, failed_codes

    batch_items = list(range_groups.items())

    for key, symbols in batch_items:
        try:
            success, failed, data = fetch_single_batch(key, symbols)
            del success
            for symbol, df in data.items():
                if symbol in results and not results[symbol].empty:
                    results[symbol] = pd.concat([results[symbol], df])
                    results[symbol] = results[symbol][
                        ~results[symbol].index.duplicated(keep="last")
                    ]
                    results[symbol].sort_index(inplace=True)
                else:
                    results[symbol] = df
            failed_codes.extend(failed)
        except Exception as e:
            logger.error(f"批次执行失败 {key}: {type(e).__name__}: {e}")
            failed_codes.extend(symbols)

    return results, failed_codes


def execute_kline_query(
    symbol_list: list[str],
    interval: str,
    start_date: str | None,
    end_date: str | None,
    max_concurrent: int | None = None,
) -> dict[str, pd.DataFrame]:
    """优化的 K 线查询：同步兼容入口，内部桥接到 async 实现。"""
    return asyncio.run(
        execute_kline_query_async(
            symbol_list=symbol_list,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            max_concurrent=max_concurrent,
        )
    )


async def execute_kline_query_async(
    symbol_list: list[str],
    interval: str,
    start_date: str | None,
    end_date: str | None,
    max_concurrent: int | None = None,
    async_db_manager: AsyncDatabaseManager | None = None,
) -> dict[str, pd.DataFrame]:
    """优化的 K 线查询：按缺失区间分组并发获取（async 入口，SDK 用线程池）。

    Args:
        symbol_list: 证券代码列表
        interval: K 线周期
        start_date: 开始日期
        end_date: 结束日期
        max_concurrent: 最大并发数
        async_db_manager: AsyncDatabaseManager 实例（可选，用于依赖注入）

    Returns:
        以证券代码为键的 K 线数据 DataFrame 字典
    """
    if max_concurrent is None:
        max_concurrent = int(os.getenv("GALAXY_KLINE_MAX_CONCURRENT", "5"))

    # 使用注入的 db_manager 或获取默认实例
    from galaxy_db_sync.database.core.async_connection import async_db_manager as default_async_db_manager
    db = async_db_manager or default_async_db_manager

    # 创建 KlineService 实例（依赖注入模式）
    kline_service = KlineService(db)

    # 使用 async 数据库查询（不再是 Phase 3 前存根）
    db_data = await kline_service.query_kline_from_db(
        symbols=symbol_list,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )

    completeness_results: dict[str, CompletenessResult] = {}
    symbols_needing_sync: list[str] = []

    for symbol in symbol_list:
        completeness_result = await kline_completeness_checker.check_async(
            symbol=symbol,
            interval=interval,
            start_date=cast(str, start_date),
            end_date=cast(str, end_date),
        )
        completeness_results[symbol] = completeness_result

        if not completeness_result.is_complete:
            symbols_needing_sync.append(symbol)

    if not symbols_needing_sync:
        logger.info("所有数据完整，无需 API 查询")
        return db_data

    range_groups = group_symbols_by_missing_ranges(
        {s: completeness_results[s] for s in symbols_needing_sync},
        interval,
    )

    total_pairs = sum(len(v) for v in range_groups.values())
    logger.info(f"分组: {len(range_groups)} 个缺失区间, {total_pairs} 个 symbol-区间对")
    for key, symbols in range_groups.items():
        logger.debug(f"  {key[0]}-{key[1]}: {len(symbols)} symbols")

    # SDK 批量抓取使用 asyncio.to_thread 包装 ThreadPoolExecutor 实现
    api_data, failed_codes = await asyncio.to_thread(
        batch_fetch_kline_data,
        range_groups,
        max_workers=max_concurrent,
    )

    if failed_codes:
        logger.warning(f"获取失败 {len(failed_codes)} 个 symbols: {failed_codes[:10]}...")

    return kline_service.merge_db_and_api_data(db_data, api_data)


def query_kline_with_results(
    code_list: list[str],
    begin_date: int,
    end_date: int,
    interval: str,
    begin_time: int | None = None,
    end_time: int | None = None,
) -> KlineQueryResult:
    """使用结果封装类型查询K线数据（同步实现，直接调用 SDK）。"""
    from galaxy_db_sync.shared_kernel.exceptions import SDKError

    try:
        kline_dict = amazing_data_client.get_kline(
            code_list=code_list,
            begin_date=begin_date,
            end_date=end_date,
            interval=interval,
            begin_time=begin_time,
            end_time=end_time,
        )
    except TypeError as e:
        if "'NoneType' object cannot be interpreted as an integer" in str(e):
            logger.error(f"API调用遇到已知SDK错误: {e}")
            results = {}
            for code in code_list:
                error = KlineError(
                    error_code=KlineErrorCode.SDK_BUG_ERROR,
                    message=f"AmazingData SDK内部错误: {str(e)}. 这是已知问题，可能需要重试。",
                    affected_codes=[code],
                )
                results[code] = KlineItemResult.from_error(
                    code=code, error=error, interval=interval
                )
            return KlineQueryResult(results=results)
        raise
    except SDKError as e:
        logger.error(f"API调用失败 (SDK): {e}")
        results = {}
        for code in code_list:
            error = KlineError(
                error_code=KlineErrorCode.SDK_BUG_ERROR,
                message=f"SDK错误: {e.message}",
                affected_codes=[code],
            )
            results[code] = KlineItemResult.from_error(
                code=code, error=error, interval=interval
            )
        return KlineQueryResult(results=results)
    except Exception as e:
        logger.error(f"API调用失败: {type(e).__name__}: {e}")
        results = {}
        for code in code_list:
            error = KlineError(
                error_code=KlineErrorCode.SDK_BUG_ERROR,
                message=f"API调用失败: {str(e)}",
                affected_codes=[code],
            )
            results[code] = KlineItemResult.from_error(
                code=code, error=error, interval=interval
            )
        return KlineQueryResult(results=results)

    results = {}

    for code in code_list:
        if code in kline_dict:
            data = kline_dict[code]
            if data is not None and not data.empty:
                results[code] = KlineItemResult.from_success(
                    code=code, data=data, interval=interval
                )
            else:
                error = KlineError(
                    error_code=KlineErrorCode.NO_DATA_FOUND,
                    message=f"代码 {code} 在指定日期范围内无数据",
                    affected_codes=[code],
                )
                results[code] = KlineItemResult.from_error(
                    code=code, error=error, interval=interval
                )
        else:
            error = KlineError(
                error_code=KlineErrorCode.INVALID_CODE,
                message=f"证券代码无效: {code}",
                affected_codes=[code],
            )
            results[code] = KlineItemResult.from_error(
                code=code, error=error, interval=interval
            )

    return KlineQueryResult(results=results)


async def query_kline_with_results_async(
    code_list: list[str],
    begin_date: int,
    end_date: int,
    interval: str,
    begin_time: int | None = None,
    end_time: int | None = None,
) -> KlineQueryResult:
    """使用结果封装类型异步查询K线数据（包装同步 SDK）。"""
    return await asyncio.to_thread(
        query_kline_with_results,
        code_list=code_list,
        begin_date=begin_date,
        end_date=end_date,
        interval=interval,
        begin_time=begin_time,
        end_time=end_time,
    )
