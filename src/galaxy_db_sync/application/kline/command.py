"""K 线命令模块.

此模块提供 `kline` CLI 主流程，并保留面向程序内调用的查询兼容入口。
当前命令层主语义已统一为：先做完整性检查，再按缺失区间触发同步。
"""

import argparse
import asyncio
import logging
from typing import Any, cast

from galaxy_db_sync.database.core.async_connection import async_db_manager
from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.services.kline_completeness_checker import (
    kline_completeness_checker,
)
from galaxy_db_sync.shared_kernel.enums.interval import Interval
from galaxy_db_sync.shared_kernel.enums.security_type import SecurityType
from galaxy_db_sync.shared_kernel.utils import (
    get_valid_symbols_from_input,
    parse_symbols,
    validate_symbol_format,
)
from galaxy_db_sync.shared_kernel.utils.time_parser import (
    pad_date_to_full_format,
    resolve_default_end_date_for_interval,
    resolve_default_start_date_for_interval,
    validate_date_range,
)

from .parser import IntervalOption
from .result import KlineSyncResult
from .sync_orchestrator import execute_kline_query, sync_kline_data

logger = logging.getLogger(__name__)


class KLineCommandService:
    """兼容性查询入口。

    该类保留给程序内按单 symbol 查询 K 线结果的调用方使用，
    不是当前 `kline` CLI 的主同步编排入口。
    """

    def __init__(self) -> None:
        """初始化K线命令服务."""
        db_manager.initialize()
        self.logger = logging.getLogger(__name__)

    def get_kline(
        self,
        symbol: str,
        interval: "Interval",
        start_date: str | None,
        end_date: str | None,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """按单 symbol 返回查询结果.

        这是兼容性查询接口，会复用 `execute_kline_query()`；
        CLI 主流程仍以 `handle_kline_command()` 为准。
        """
        # 将Interval枚举转换为字符串
        interval_str = interval.name.lower()

        # 推导默认日期
        adjusted_start = resolve_default_start_date_for_interval([symbol], interval_str, start_date)
        adjusted_end = end_date

        # 执行查询
        result = execute_kline_query(
            symbol_list=[symbol],
            interval=interval_str,
            start_date=adjusted_start,
            end_date=adjusted_end,
        )

        # 过滤字段
        if fields and result and symbol in result:
            df = result[symbol]
            if df is not None and not df.empty:
                available_fields = [col for col in fields if col in df.columns]
                filtered_df = df[available_fields].copy()
                result[symbol] = filtered_df

        # 转换为字典格式
        if result and symbol in result and result[symbol] is not None:
            df = result[symbol]
            if not df.empty:
                return {
                    "data": df.to_dict("records"),
                    "symbol": symbol,
                    "interval": interval_str,
                    "start_date": adjusted_start,
                    "end_date": adjusted_end,
                }

        return {
            "data": [],
            "symbol": symbol,
            "interval": interval_str,
            "start_date": adjusted_start,
            "end_date": adjusted_end,
        }


def handle_kline_command(args: argparse.Namespace) -> int:
    """处理 kline 命令.

    当前主流程：
    1. 参数检查与 symbols 校验
    2. 调用完整性检查器判断数据库是否已完整覆盖请求范围
    3. 若完整则直接返回成功
    4. 若不完整则按缺失区间触发同步
    5. 输出同步摘要
    """
    try:
        # 1. 参数检查
        interval_option_map = {p.name.lower(): p for p in IntervalOption}
        if args.interval not in interval_option_map:
            logger.error(f"无效的 interval 参数: {args.interval}")
            logger.error(f"支持的参数值: {list(interval_option_map.keys())}")
            return 1

        database_initialized = False

        # 解析 symbols 参数
        parsed_symbols = parse_symbols(args.symbols)
        input_symbol_list = [item[1] for item in parsed_symbols]

        if not input_symbol_list:
            logger.error("未提供任何证券代码")
            return 1

        # 格式校验
        for symbol in input_symbol_list:
            if symbol not in [
                sec_type.name for sec_type in SecurityType
            ] and not validate_symbol_format(symbol):
                logger.error(f"证券代码格式无效: {symbol}")
                return 1

        # 2. 推导 start/end
        interval_enum = Interval(args.interval)

        # 长周期需要数据库初始化（交易日历查询）
        if interval_enum in {Interval.WEEK, Interval.MONTH, Interval.SEASON, Interval.YEAR}:
            db_manager.initialize()
            database_initialized = True

        raw_start = resolve_default_start_date_for_interval(
            input_symbol_list, args.interval, args.start
        )
        raw_end = resolve_default_end_date_for_interval(args.interval, args.end)

        logger.info(f"日期参数: start={raw_start}, end={raw_end}")

        # 3. 精度校验
        date_errors = validate_date_range(raw_start, raw_end, args.interval)
        if date_errors:
            for error in date_errors:
                logger.error(error)
            return 1

        # 4. 补全为完整 8 位日期
        full_start_for_codes = cast(
            str,
            pad_date_to_full_format(raw_start, args.interval, is_end=False),
        )
        full_end_for_codes = cast(
            str,
            pad_date_to_full_format(raw_end, args.interval, is_end=True),
        )

        # 获取有效的证券代码列表
        valid_symbols = get_valid_symbols_from_input(
            input_symbol_list, full_start_for_codes, full_end_for_codes
        )

        if not valid_symbols:
            logger.error("未获取到任何有效的证券代码")
            return 1

        # 再次推导 start
        adjusted_start = resolve_default_start_date_for_interval(
            valid_symbols, args.interval, args.start
        )
        adjusted_end = raw_end

        full_start = cast(
            str,
            pad_date_to_full_format(adjusted_start, args.interval, is_end=False),
        )
        full_end = cast(
            str,
            pad_date_to_full_format(adjusted_end, args.interval, is_end=True),
        )

        logger.info(f"将获取 {len(valid_symbols)} 个证券的 K 线数据")

        if not database_initialized:
            db_manager.initialize()
            logger.info("数据库已初始化")

        # 获取上市日期
        listing_dates = _get_listing_dates(valid_symbols)

        # 完整性检查
        completeness_results = {}
        complete_symbols = []
        incomplete_symbols = []
        empty_symbols = []
        adjusted_symbols = []

        for symbol in valid_symbols:
            symbol_start = full_start
            listing_date = listing_dates.get(symbol)
            if listing_date and listing_date > full_start:
                logger.debug(
                    f"{symbol}: 上市日期 {listing_date} 晚于请求开始日期 {full_start}，调整范围"
                )
                symbol_start = listing_date
                if symbol not in adjusted_symbols:
                    adjusted_symbols.append(symbol)

            completeness_result = kline_completeness_checker.check(
                symbol=symbol,
                interval=args.interval,
                start_date=symbol_start,
                end_date=full_end,
            )
            completeness_results[symbol] = completeness_result

            if completeness_result.is_complete:
                complete_symbols.append(symbol)
            elif completeness_result.coverage_ratio == 0.0:
                empty_symbols.append(symbol)
            else:
                incomplete_symbols.append(symbol)

        # 整合输出日志
        total_count = len(valid_symbols)
        complete_count = len(complete_symbols)
        incomplete_count = len(incomplete_symbols)
        empty_count = len(empty_symbols)

        logger.info(
            f"完整性检查完成: 共 {total_count} 只证券, "
            f"完整 {complete_count}, 部分缺失 {incomplete_count}, 无数据 {empty_count}"
        )

        if adjusted_symbols:
            logger.info(f"因上市日期调整范围的证券: {len(adjusted_symbols)} 只")

        if incomplete_symbols:
            max_display = 10
            for symbol in incomplete_symbols[:max_display]:
                result = completeness_results[symbol]
                logger.info(
                    f"  {symbol}: 缺失 {result.missing_count}/{result.total_count} "
                    f"({result.coverage_ratio:.1%}), {len(result.missing_ranges)} 个缺失区间"
                )
            if len(incomplete_symbols) > max_display:
                logger.info(f"  ... 还有 {len(incomplete_symbols) - max_display} 只证券数据不完整")

        if empty_symbols:
            max_display = 5
            logger.info(
                f"无数据证券 ({empty_count} 只，可能未上市/退市): "
                f"{', '.join(empty_symbols[:max_display])}"
                f"{'...' if len(empty_symbols) > max_display else ''}"
            )

        all_data_complete = incomplete_count == 0 and empty_count == 0

        if all_data_complete:
            logger.info(f"数据已完整，无需同步 ({complete_count} 只证券)")
            return 0
        else:
            sync_result = sync_kline_data(
                completeness_results=completeness_results,
                interval=args.interval,
                full_start=full_start,
                full_end=full_end,
            )

            logger.info("=" * 50)
            logger.info("同步完成！")
            logger.info("-" * 50)
            logger.info(f"同步成功代码数: {sync_result.success_count}")
            logger.info(f"同步成功记录数: {sync_result.synced_records:,} 条")
            logger.info(f"同步失败代码数: {len(sync_result.failed_codes)}")

            if sync_result.failed_codes:
                max_display = 10
                failed_str = ", ".join(sync_result.failed_codes[:max_display])
                if len(sync_result.failed_codes) > max_display:
                    failed_str += f" ... (共 {len(sync_result.failed_codes)} 只)"
                logger.info(f"失败代码: {failed_str}")
            logger.info("=" * 50)

        return 0

    except asyncio.CancelledError:
        logger.warning("操作被取消")
        return 130
    except Exception as e:
        logger.error(f"命令执行失败: {e}")
        import traceback

        traceback.print_exc()
        return 1


def _get_listing_dates(symbols: list[str]) -> dict[str, str | None]:
    """获取证券上市日期.

    根据证券代码后缀判断类型，调用对应的 API 获取上市日期。

    Args:
        symbols: 证券代码列表

    Returns:
        dict {symbol: list_day} 上市日期字符串 (YYYYMMDD)
    """
    from galaxy_db_sync.amazing_data.api.client import amazing_data_client

    sh_ETF_symbols = []
    sz_ETF_symbols = []
    sh_stock_symbols = []
    sz_stock_symbols = []
    bj_stock_symbols = []
    other_symbols = []

    for symbol in symbols:
        if symbol.endswith(".SH"):
            if symbol.startswith("51") or symbol.startswith("58"):
                sh_ETF_symbols.append(symbol)
            else:
                sh_stock_symbols.append(symbol)
        elif symbol.endswith(".SZ"):
            if symbol.startswith("15") or symbol.startswith("16"):
                sz_ETF_symbols.append(symbol)
            else:
                sz_stock_symbols.append(symbol)
        elif symbol.endswith(".BJ"):
            bj_stock_symbols.append(symbol)
        else:
            other_symbols.append(symbol)

    listing_dates: dict[str, str | None] = {}

    all_etf_symbols = sh_ETF_symbols + sz_ETF_symbols
    if all_etf_symbols:
        try:
            etf_dates = amazing_data_client.get_listing_dates(
                all_etf_symbols, security_type="EXTRA_ETF"
            )
            listing_dates.update(etf_dates)
        except Exception as e:
            logger.warning(f"获取 ETF 上市日期失败: {e}")

    # A 股上市日期
    all_stock_symbols = sh_stock_symbols + sz_stock_symbols + bj_stock_symbols
    if all_stock_symbols:
        try:
            stock_dates = amazing_data_client.get_listing_dates(
                all_stock_symbols, security_type="EXTRA_STOCK_A"
            )
            listing_dates.update(stock_dates)
        except Exception as e:
            logger.warning(f"获取股票上市日期失败: {e}")

    for symbol in other_symbols:
        listing_dates[symbol] = None

    return listing_dates


async def sync_kline_data_async(
    completeness_results: dict[str, Any],
    interval: str,
    full_start: str,
    full_end: str,
) -> KlineSyncResult:
    """异步版本的 K 线数据同步.

    直接调用异步实现，无需 to_thread 包装。

    Args:
        completeness_results: 每个 symbol 对应的完整性检查结果
        interval: K 线周期
        full_start: 补全后的开始日期（8 位 YYYYMMDD）
        full_end: 补全后的结束日期（8 位 YYYYMMDD）

    Returns:
        KlineSyncResult: 同步结果
    """
    from .sync_orchestrator import sync_kline_data_async_impl
    return await sync_kline_data_async_impl(
        completeness_results=completeness_results,
        interval=interval,
        full_start=full_start,
        full_end=full_end,
    )


async def handle_kline_command_async(args: argparse.Namespace) -> int:
    """异步版本的 kline 命令处理.

    Per ASYNC-05: CLI 使用 asyncio.run() 驱动异步命令。
    Per COMPAT-01: 保持相同的参数、输出和退出码。

    与 handle_kline_command 的差异:
    - 使用 async_db_manager 而非 sync db_manager
    - 使用 asyncio.to_thread 包装 sync SDK 调用 (_get_listing_dates)
    - 使用 asyncio.to_thread 包装 sync completeness checker
    - 使用 sync_kline_data_async 替代 sync_kline_data
    """
    try:
        # 1. 参数检查（同步，与原版相同）
        interval_option_map = {p.name.lower(): p for p in IntervalOption}
        if args.interval not in interval_option_map:
            logger.error(f"无效的 interval 参数: {args.interval}")
            logger.error(f"支持的参数值: {list(interval_option_map.keys())}")
            return 1

        database_initialized = False

        # 解析 symbols 参数（同步）
        parsed_symbols = parse_symbols(args.symbols)
        input_symbol_list = [item[1] for item in parsed_symbols]

        if not input_symbol_list:
            logger.error("未提供任何证券代码")
            return 1

        # 格式校验（同步）
        for symbol in input_symbol_list:
            if symbol not in [
                sec_type.name for sec_type in SecurityType
            ] and not validate_symbol_format(symbol):
                logger.error(f"证券代码格式无效: {symbol}")
                return 1

        # 2. 推导 start/end（同步，与原版相同）
        interval_enum = Interval(args.interval)

        # 长周期需要数据库初始化（交易日历查询）
        if interval_enum in {Interval.WEEK, Interval.MONTH, Interval.SEASON, Interval.YEAR}:
            async_db_manager.initialize()
            db_manager.initialize()
            database_initialized = True

        raw_start = resolve_default_start_date_for_interval(
            input_symbol_list, args.interval, args.start
        )
        raw_end = resolve_default_end_date_for_interval(args.interval, args.end)

        logger.info(f"日期参数: start={raw_start}, end={raw_end}")

        # 3. 精度校验（同步）
        date_errors = validate_date_range(raw_start, raw_end, args.interval)
        if date_errors:
            for error in date_errors:
                logger.error(error)
            return 1

        # 4. 补全为完整 8 位日期（同步）
        full_start_for_codes = cast(
            str,
            pad_date_to_full_format(raw_start, args.interval, is_end=False),
        )
        full_end_for_codes = cast(
            str,
            pad_date_to_full_format(raw_end, args.interval, is_end=True),
        )

        # 获取有效的证券代码列表（同步）
        valid_symbols = get_valid_symbols_from_input(
            input_symbol_list, full_start_for_codes, full_end_for_codes
        )

        if not valid_symbols:
            logger.error("未获取到任何有效的证券代码")
            return 1

        # 再次推导 start（同步）
        adjusted_start = resolve_default_start_date_for_interval(
            valid_symbols, args.interval, args.start
        )
        adjusted_end = raw_end

        full_start = cast(
            str,
            pad_date_to_full_format(adjusted_start, args.interval, is_end=False),
        )
        full_end = cast(
            str,
            pad_date_to_full_format(adjusted_end, args.interval, is_end=True),
        )

        logger.info(f"将获取 {len(valid_symbols)} 个证券的 K 线数据")

        if not database_initialized:
            async_db_manager.initialize()
            db_manager.initialize()
            logger.info("数据库已初始化")

        # 获取上市日期（async 包装 sync SDK 调用）
        listing_dates = await asyncio.to_thread(_get_listing_dates, valid_symbols)

        # 完整性检查（async 包装 sync checker）
        completeness_results = {}
        complete_symbols = []
        incomplete_symbols = []
        empty_symbols = []
        adjusted_symbols = []

        for symbol in valid_symbols:
            symbol_start = full_start
            listing_date = listing_dates.get(symbol)
            if listing_date and listing_date > full_start:
                logger.debug(
                    f"{symbol}: 上市日期 {listing_date} 晚于请求开始日期 {full_start}，调整范围"
                )
                symbol_start = listing_date
                if symbol not in adjusted_symbols:
                    adjusted_symbols.append(symbol)

            completeness_result = await kline_completeness_checker.check_async(
                symbol=symbol,
                interval=args.interval,
                start_date=symbol_start,
                end_date=full_end,
            )
            completeness_results[symbol] = completeness_result

            if completeness_result.is_complete:
                complete_symbols.append(symbol)
            elif completeness_result.coverage_ratio == 0.0:
                empty_symbols.append(symbol)
            else:
                incomplete_symbols.append(symbol)

        # 整合输出日志（同步）
        total_count = len(valid_symbols)
        complete_count = len(complete_symbols)
        incomplete_count = len(incomplete_symbols)
        empty_count = len(empty_symbols)

        logger.info(
            f"完整性检查完成: 共 {total_count} 只证券, "
            f"完整 {complete_count}, 部分缺失 {incomplete_count}, 无数据 {empty_count}"
        )

        if adjusted_symbols:
            logger.info(f"因上市日期调整范围的证券: {len(adjusted_symbols)} 只")

        if incomplete_symbols:
            max_display = 10
            for symbol in incomplete_symbols[:max_display]:
                result = completeness_results[symbol]
                logger.info(
                    f"  {symbol}: 缺失 {result.missing_count}/{result.total_count} "
                    f"({result.coverage_ratio:.1%}), {len(result.missing_ranges)} 个缺失区间"
                )
            if len(incomplete_symbols) > max_display:
                logger.info(f"  ... 还有 {len(incomplete_symbols) - max_display} 只证券数据不完整")

        if empty_symbols:
            max_display = 5
            logger.info(
                f"无数据证券 ({empty_count} 只，可能未上市/退市): "
                f"{', '.join(empty_symbols[:max_display])}"
                f"{'...' if len(empty_symbols) > max_display else ''}"
            )

        all_data_complete = incomplete_count == 0 and empty_count == 0

        if all_data_complete:
            logger.info(f"数据已完整，无需同步 ({complete_count} 只证券)")
            return 0
        else:
            sync_result = await sync_kline_data_async(
                completeness_results=completeness_results,
                interval=args.interval,
                full_start=full_start,
                full_end=full_end,
            )

            logger.info("=" * 50)
            logger.info("同步完成！")
            logger.info("-" * 50)
            logger.info(f"同步成功代码数: {sync_result.success_count}")
            logger.info(f"同步成功记录数: {sync_result.synced_records:,} 条")
            logger.info(f"同步失败代码数: {len(sync_result.failed_codes)}")

            if sync_result.failed_codes:
                max_display = 10
                failed_str = ", ".join(sync_result.failed_codes[:max_display])
                if len(sync_result.failed_codes) > max_display:
                    failed_str += f" ... (共 {len(sync_result.failed_codes)} 只)"
                logger.info(f"失败代码: {failed_str}")
            logger.info("=" * 50)

        return 0

    except asyncio.CancelledError:
        logger.warning("操作被取消")
        return 130
    except Exception as e:
        logger.error(f"命令执行失败: {e}")
        import traceback

        traceback.print_exc()
        return 1
