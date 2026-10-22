"""K 线命令模块.

此模块提供 `kline` CLI 主流程，并保留面向程序内调用的查询兼容入口。
当前命令层主语义已统一为：先做完整性检查，再按缺失区间触发同步。
"""

import argparse
import asyncio
import logging
from datetime import date, timedelta
from typing import Any

from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.domain.ports.reference_provider import ReferenceProviderPort
from galaxy_core.database.services.trading_calendar import TradingCalendarService
from galaxy_core.shared_kernel.enums.security_type import SecurityType
from galaxy_core.shared_kernel.utils import (
    parse_symbols,
    validate_symbol_format,
)
from galaxy_core.shared_kernel.utils.time_parser import (
    resolve_default_end_date_for_interval,
    resolve_default_start_date_for_interval,
    validate_date_range,
)

from .parser import IntervalOption
from .result import KlineSyncResult
from .sync_common import prepare_sync_args, resolve_symbols

logger = logging.getLogger(__name__)


def handle_kline_command(args: argparse.Namespace) -> int:
    """处理 kline 命令.

    .. deprecated::
        此同步函数已废弃，请使用 handle_kline_command_async。
        保留仅为向后兼容。

    当前主流程：
    1. 参数检查与 symbols 校验
    2. 通过 DI 容器获取服务
    3. 调用 handle_kline_command_async 执行同步
    """
    try:
        # 1. 参数检查
        interval_option_map = {p.name.lower(): p for p in IntervalOption}
        raw_intervals = args.interval if isinstance(args.interval, list) else [args.interval]
        invalid_intervals = [i for i in raw_intervals if i not in interval_option_map]
        if invalid_intervals:
            logger.error(f"无效的 interval 参数: {invalid_intervals}")
            logger.error(f"支持的参数值: {list(interval_option_map.keys())}")
            return 1

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

        # 2. 创建 DI 容器并获取服务
        from galaxy_core.di.container import create_container
        container = create_container()

        # 3. 调用异步版本
        return asyncio.run(
            handle_kline_command_async(
                args,
                kline_service=container.kline_service(),
                async_db_manager=container.db_manager(),
                reference_provider=container.reference_provider(),
                trading_calendar_service=container.trading_calendar_service(),
            )
        )

    except asyncio.CancelledError:
        logger.warning("操作被取消")
        return 130
    except Exception:
        logger.exception("命令执行失败")
        return 1


async def handle_kline_command_async(
    args: argparse.Namespace,
    kline_service: Any = None,
    async_db_manager: AsyncDatabaseManager | None = None,
    reference_provider: ReferenceProviderPort | None = None,
    trading_calendar_service: TradingCalendarService | None = None,
) -> int:
    """异步版本的 kline 命令处理 — 新版精简流程.

    流程:
    1. 解析 symbols 和 interval
    2. security_type 展开为具体 symbols
    3. 调用 KlineDataService.sync() 执行同步

    Args:
        args: CLI 参数
        kline_service: KlineDataService 实例（DI 注入）
        async_db_manager: AsyncDatabaseManager 实例（DI 注入）
        reference_provider: ReferenceProviderPort 实例（DI 注入）
        trading_calendar_service: TradingCalendarService 实例（DI 注入）
    """
    try:
        # 1. 参数检查
        interval_option_map = {p.name.lower(): p for p in IntervalOption}
        raw_intervals = args.interval if isinstance(args.interval, list) else [args.interval]
        invalid_intervals = [i for i in raw_intervals if i not in interval_option_map]
        if invalid_intervals:
            logger.error(f"无效的 interval 参数: {invalid_intervals}")
            return 1

        # 解析 symbols
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

        # 初始化数据库
        if async_db_manager is not None:
            async_db_manager.initialize()

        # 2. 模式校验
        has_auto = getattr(args, "auto", False)

        if has_auto and (args.start or args.end):
            logger.error("--auto 与 --start/--end 互斥，不能同时使用")
            return 1

        # 3. 解析 symbols — SecurityType 展开 + 具体符号保留
        yesterday = date.today() - timedelta(days=1)
        valid_symbols = await resolve_symbols(
            input_symbol_list, reference_provider, yesterday
        )

        if not valid_symbols:
            logger.error("未获取到任何有效的证券代码")
            return 1

        # 4. 对每个 interval 执行同步
        if kline_service is None:
            logger.error("kline_service 未注入")
            return 1

        total_success = 0
        total_records = 0
        all_failed: list[str] = []

        for interval_str in raw_intervals:
            # 日期解析与校验（提供了 start/end 时解析默认值）
            if args.start or args.end:
                raw_start = resolve_default_start_date_for_interval(
                    valid_symbols, interval_str, args.start
                )
                raw_end = await resolve_default_end_date_for_interval(
                    interval_str, args.end, trading_calendar=trading_calendar_service
                )
                date_errors = await validate_date_range(
                    raw_start, raw_end, interval_str, trading_calendar=trading_calendar_service
                )
                if date_errors:
                    for error in date_errors:
                        logger.error(error)
                    return 1
            else:
                raw_start = args.start
                raw_end = args.end

            logger.info(f"将同步 {len(valid_symbols)} 只证券的 {interval_str} K 线数据")

            domain_interval, expanded_start, expanded_end = prepare_sync_args(
                interval_str, raw_start, raw_end
            )
            sync_result = await kline_service.sync(
                symbols=valid_symbols,
                interval=domain_interval,
                start=expanded_start,
                end=expanded_end,
            )

            total_success += sync_result.success_count
            total_records += sync_result.synced_records
            all_failed.extend(sync_result.failed_codes)

        logger.info(
            f"同步完成: {total_success}/{len(valid_symbols) * len(raw_intervals)} 成功, "
            f"{total_records} 条记录"
        )
        if all_failed:
            logger.warning(f"失败: {all_failed[:10]}")

        return 0

    except asyncio.CancelledError:
        logger.warning("操作被取消")
        return 130
    except Exception:
        logger.exception("命令执行失败")
        return 1


def _parse_date_value(value):
    """解析日期值."""

    if value is None:
        return None
    try:
        import pandas as pd
        if pd.isna(value):
            return None
    except (ImportError, TypeError):
        pass

    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        value = str(int(value))
    if isinstance(value, str):
        value = value.strip()
        if len(value) == 8:
            return date(int(value[:4]), int(value[4:6]), int(value[6:]))
    return None
