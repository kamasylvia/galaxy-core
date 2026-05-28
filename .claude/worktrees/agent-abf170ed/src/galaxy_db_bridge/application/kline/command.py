"""K 线命令模块.

此模块提供 `kline` CLI 主流程，并保留面向程序内调用的查询兼容入口。
当前命令层主语义已统一为：先做完整性检查，再按缺失区间触发同步。
"""

import argparse
import logging
from typing import Any, Dict, List, Optional
from enum import Enum

import AmazingData as ad
import pandas as pd
from galaxy_db_bridge.amazing_data.api.client import amazing_data_client


# 定义 Interval 枚举用于命令行选项
class IntervalOption(Enum):
    """
    数据周期枚举 - 用于命令行界面
    """

    MIN1 = "min1"
    MIN3 = "min3"
    MIN5 = "min5"
    MIN10 = "min10"
    MIN15 = "min15"
    MIN30 = "min30"
    MIN60 = "min60"
    MIN120 = "min120"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    SEASON = "season"
    YEAR = "year"


def get_sdk_interval_value(interval_option):
    """
    获取 AmazingData SDK 中真实的 interval 值
    """
    if not hasattr(ad, "constant"):
        raise RuntimeError("AmazingData SDK constants are unavailable: missing ad.constant")

    if not hasattr(ad.constant, "Period"):
        raise RuntimeError(
            "AmazingData SDK constants are unavailable: missing ad.constant.Period"
        )

    sdk_period = ad.constant.Period
    required_members = {
        IntervalOption.MIN1: "min1",
        IntervalOption.MIN3: "min3",
        IntervalOption.MIN5: "min5",
        IntervalOption.MIN10: "min10",
        IntervalOption.MIN15: "min15",
        IntervalOption.MIN30: "min30",
        IntervalOption.MIN60: "min60",
        IntervalOption.MIN120: "min120",
        IntervalOption.DAY: "day",
        IntervalOption.WEEK: "week",
        IntervalOption.MONTH: "month",
        IntervalOption.SEASON: "season",
        IntervalOption.YEAR: "year",
    }

    if interval_option not in required_members:
        raise RuntimeError(f"Unsupported interval option: {interval_option}")

    member_name = required_members[interval_option]
    if not hasattr(sdk_period, member_name):
        raise RuntimeError(
            f"AmazingData SDK constants are unavailable: missing ad.constant.Period.{member_name}"
        )

    return getattr(sdk_period, member_name).value


class KLineCommandService:
    """兼容性查询入口。

    该类保留给程序内按单 symbol 查询 K 线结果的调用方使用，
    不是当前 `kline` CLI 的主同步编排入口。
    """

    def __init__(self):
        """初始化K线命令服务."""
        from galaxy_db_bridge.database.core.connection import db_manager

        db_manager.initialize()
        self.logger = logging.getLogger(__name__)

    def get_kline(
        self,
        symbol: str,
        interval: "Interval",
        start_date: Optional[str],
        end_date: Optional[str],
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """按单 symbol 返回查询结果。

        这是兼容性查询接口，会复用 `execute_kline_query()`；
        CLI 主流程仍以 `handle_kline_command()` 为准。
        """
        from galaxy_db_bridge.shared_kernel.enums.interval import Interval

        # 将Interval枚举转换为字符串
        interval_str = interval.name.lower()
        interval_option = IntervalOption[interval.name]
        interval_value = get_sdk_interval_value(interval_option)

        effective_start = resolve_default_start_date([symbol], start_date)

        # 验证并调整日期参数
        adjusted_start, adjusted_end = validate_start_end_by_period(
            interval_str, effective_start, end_date
        )

        # 使用现有的函数执行查询
        result = execute_kline_query(
            symbol_list=[symbol],
            interval=interval_str,
            start_date=adjusted_start,
            end_date=adjusted_end,
            interval_value=interval_value,
        )

        # 如果指定了字段，则过滤数据
        if fields and result and symbol in result:
            df = result[symbol]
            if df is not None and not df.empty:
                # 确保字段存在于DataFrame中
                available_fields = [col for col in fields if col in df.columns]
                filtered_df = df[available_fields].copy()
                result[symbol] = filtered_df

        # 转换为字典格式返回
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


from galaxy_db_bridge.shared_kernel.utils.time_parser import (
    resolve_default_start_date,
    validate_start_end_by_period,
    validate_date_range,
)
from galaxy_db_bridge.shared_kernel.utils.symbol_validator import (
    parse_symbols,
    get_valid_symbols_from_input,
)
from galaxy_db_bridge.shared_kernel.enums.security_type import SecurityType
from galaxy_db_bridge.database.services.kline_completeness_checker import (
    kline_completeness_checker,
)
from .error import KlineError, KlineErrorCode
from .result import KlineItemResult, KlineQueryResult, KlineSyncResult

logger = logging.getLogger(__name__)


def create_kline_parser(subparsers: Any) -> Any:
    """创建 kline subparser."""
    kline_parser = subparsers.add_parser(
        "kline",
        help="获取 K 线数据并存入数据库",
        description="获取指定证券的 K 线数据，支持单代码、代码列表、SecurityType 或混合列表。"
        "数据自动存入数据库，增量获取缺失数据。",
    )

    # 必选参数: symbols
    kline_parser.add_argument(
        "symbols",
        type=str,
        help="证券代码，支持：\n"
        '- 单代码: "600000.SH"\n'
        '- 代码列表: "[600000.SH, 000001.SZ]" 或 "600000.SH,000001.SZ"\n'
        '- SecurityType: "SH_A", "SZ_ETF", "EXTRA_STOCK_A" 等\n'
        '- 混合列表: "[600000.SH, SH_ETF]"',
    )

    # 可选参数: interval
    interval_choices = [p.name.lower() for p in IntervalOption]
    kline_parser.add_argument(
        "--interval",
        choices=interval_choices,
        default="day",
        help=f"K 线周期，默认为 day。可选值: {', '.join(interval_choices)}",
    )

    # 可选参数: start
    kline_parser.add_argument(
        "--start",
        default=None,
        help="开始日期/时间。\n"
        "- 年线: 4 位数字 (YYYY)\n"
        "- 季线/月线: 6 位数字 (YYYYMM)\n"
        "- 日线/周线: 8 位数字 (YYYYMMDD)\n"
        "- 小时/两小时线: 10 位数字 (YYYYMMDDHH)\n"
        "- 分钟线: 12 位数字 (YYYYMMDDHHMM)\n"
        "默认按证券类型使用 AmazingData 数据起点。",
    )

    # 可选参数: end
    kline_parser.add_argument(
        "--end",
        default=None,
        help="结束日期/时间。\n"
        "- 年线: 4 位数字 (YYYY)\n"
        "- 季线/月线: 6 位数字 (YYYYMM)\n"
        "- 日线/周线: 8 位数字 (YYYYMMDD)\n"
        "- 小时/两小时线: 10 位数字 (YYYYMMDDHH)\n"
        "- 分钟线: 12 位数字 (YYYYMMDDHHMM)\n"
        "默认为昨天。",
    )

    return kline_parser


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
        # 验证 interval 参数的有效性
        interval_option_map = {p.name.lower(): p for p in IntervalOption}
        if args.interval not in interval_option_map:
            logger.error(f"无效的 interval 参数: {args.interval}")
            logger.error(f"支持的参数值: {list(interval_option_map.keys())}")
            return 1

        # 解析 symbols 参数
        parsed_symbols = parse_symbols(args.symbols)
        input_symbol_list = [item[1] for item in parsed_symbols]  # 获取所有输入的符号

        # 进行基本的参数校验（不触发API调用）
        # （期权类型现在被支持，不再需要拒绝）

        # 检查输入的证券代码是否为空或无效格式
        if not input_symbol_list:
            logger.error("未提供任何证券代码")
            return 1

        # 进行基础格式校验（不触发API调用）
        from galaxy_db_bridge.shared_kernel.utils.symbol_validator import (
            validate_symbol_format,
        )

        for symbol in input_symbol_list:
            if symbol not in [
                sec_type.name for sec_type in SecurityType
            ]:  # 如果不是SecurityType
                if not validate_symbol_format(symbol):
                    logger.error(f"证券代码格式无效: {symbol}")
                    return 1

        if args.start is None:
            preliminary_start = resolve_default_start_date(input_symbol_list, None)
            preliminary_start, preliminary_end = validate_start_end_by_period(
                args.interval, preliminary_start, args.end
            )
        else:
            preliminary_start, preliminary_end = validate_start_end_by_period(
                args.interval, args.start, args.end
            )

        # 获取有效的证券代码列表（这部分会触发API调用，但只在基础校验通过后）
        valid_symbols = get_valid_symbols_from_input(
            input_symbol_list, preliminary_start, preliminary_end
        )

        if not valid_symbols:
            logger.error("未获取到任何有效的证券代码")
            return 1

        if args.start is None:
            effective_start = resolve_default_start_date(valid_symbols, None)
            adjusted_start, adjusted_end = validate_start_end_by_period(
                args.interval, effective_start, args.end
            )
        else:
            adjusted_start, adjusted_end = preliminary_start, preliminary_end

        # 验证日期范围
        date_errors = validate_date_range(adjusted_start, adjusted_end, args.interval)
        if date_errors:
            for error in date_errors:
                logger.error(error)
            return 1

        logger.info(f"将获取 {len(valid_symbols)} 个证券的 K 线数据")

        # 转换周期
        interval_option = interval_option_map[args.interval]
        interval_value = get_sdk_interval_value(interval_option)  # 使用新的函数获取 SDK 真实值

        # 参数校验通过后再初始化数据库
        from galaxy_db_bridge.database.core.connection import db_manager

        db_manager.initialize()
        logger.info("数据库已初始化")

        # 检查数据库中数据的完整性
        completeness_results = {}
        all_data_complete = True
        for symbol in valid_symbols:
            completeness_result = kline_completeness_checker.check(
                symbol=symbol,
                interval=args.interval,
                start_date=adjusted_start,
                end_date=adjusted_end,
            )
            completeness_results[symbol] = completeness_result

            if not completeness_result.is_complete:
                logger.info(
                    f"{symbol}: 缺失 {completeness_result.missing_count} 个数据点，"
                    f"涉及 {len(completeness_result.missing_ranges)} 个缺失区间"
                )
                all_data_complete = False

        if all_data_complete:
            # 如果数据库中已存在请求的数据且完整，直接返回成功
            logger.info(
                f"查询成功！数据库中已存在 {len(valid_symbols)} 个证券的完整 K 线数据，同步 0 条数据"
            )
            for symbol in valid_symbols:
                logger.info(f"  - {symbol}")
            return 0
        else:
            # 如果数据库中数据不完整，执行同步
            sync_result = _sync_kline_data(
                completeness_results=completeness_results,
                interval=args.interval,
                interval_value=interval_value,
            )

            # 输出详细的同步结果
            logger.info("=" * 50)
            logger.info("同步完成！")
            logger.info("-" * 50)
            logger.info(f"同步成功代码数: {sync_result.success_count}")
            logger.info(f"同步成功记录数: {sync_result.synced_records:,} 条")
            logger.info(f"同步失败代码数: {len(sync_result.failed_codes)}")

            if sync_result.failed_codes:
                logger.info("失败代码列表:")
                for code in sync_result.failed_codes:
                    logger.info(f"  - {code}")
            logger.info("=" * 50)

        return 0

    except Exception as e:
        logger.error(f"命令执行失败: {e}")
        import traceback

        traceback.print_exc()
        return 1


def _sync_kline_data(
    completeness_results: dict[str, Any],
    interval: str,
    interval_value: str,
) -> "KlineSyncResult":
    """同步 K 线数据.

    Args:
        completeness_results: 每个 symbol 对应的完整性检查结果
        interval: K 线周期
        interval_value: 数据周期对应的 SDK 整数值

    Returns:
        KlineSyncResult: 同步结果，包含成功数量、同步记录数、失败代码列表
    """
    from galaxy_db_bridge.database.services.kline_data_sync import (
        kline_data_sync_service,
    )

    total_synced = 0
    success_count = 0
    failed_codes = []

    for symbol, completeness_result in completeness_results.items():
        try:
            if completeness_result.is_complete:
                logger.info(f"{symbol}: 数据已完整，无需同步")
                success_count += 1
                continue

            range_synced_count = 0
            for range_start, range_end in completeness_result.missing_ranges:
                synced_count = kline_data_sync_service.sync_kline_data(
                    symbol=symbol,
                    interval=interval,
                    start_date=range_start.strftime("%Y%m%d"),
                    end_date=range_end.strftime("%Y%m%d"),
                    interval_value=interval_value,
                )
                range_synced_count += synced_count
                total_synced += synced_count

            if range_synced_count > 0:
                success_count += 1
            else:
                failed_codes.append(symbol)

        except Exception as e:
            logger.error(f"{symbol}: 处理失败 - {e}")
            failed_codes.append(symbol)
            continue

    # 登出
    from galaxy_db_bridge.shared_kernel.utils.config_loader import get_config

    username = get_config("amazing_data", "username")
    amazing_data_client.logout(username)
    logger.info("已登出")

    # 记录同步结果
    logger.info(
        f"同步完成！同步成功代码数: {success_count}, 同步失败代码数: {len(failed_codes)}"
    )
    logger.info(f"共同步 {total_synced} 条 K 线数据到数据库")
    if failed_codes:
        logger.info(f"同步失败的代码: {failed_codes}")

    return KlineSyncResult(
        success_count=success_count,
        synced_records=total_synced,
        failed_codes=failed_codes,
        message=f"同步完成！成功: {success_count}, 失败: {len(failed_codes)}, 记录数: {total_synced}",
    )


def execute_kline_query(
    symbol_list: list[str],
    interval: str,
    start_date: str | None,
    end_date: str | None,
    interval_value: str,
) -> dict:
    """兼容性查询路径：返回数据库结果与按缺失区间补查后的合并结果.

    该函数主要服务于程序内查询接口，不是 CLI 主同步编排入口。
    """
    from galaxy_db_bridge.database.services.kline import kline_service

    # 从数据库查询已有数据
    db_data = kline_service.query_kline_from_db(
        symbols=symbol_list,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )

    # 识别数据库中缺失的数据范围
    api_data = {}
    for symbol in symbol_list:
        completeness_result = kline_completeness_checker.check(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
        )

        api_frames = []
        for range_start, range_end in completeness_result.missing_ranges:
            api_result = query_kline_with_results(
                code_list=[symbol],
                begin_date=int(range_start.strftime("%Y%m%d")),
                end_date=int(range_end.strftime("%Y%m%d")),
                interval=interval_value,
            )

            if symbol in api_result.results and api_result.results[symbol].success:
                api_frames.append(api_result.results[symbol].data)
            else:
                logger.warning(
                    f"API查询失败: {symbol} in range {range_start} to {range_end}"
                )

        if api_frames:
            combined_api_df = pd.concat(api_frames)
            combined_api_df = combined_api_df[
                ~combined_api_df.index.duplicated(keep="last")
            ]
            combined_api_df.sort_index(inplace=True)
            api_data[symbol] = combined_api_df

    # 合并数据库和API的数据
    merged_data = kline_service.merge_db_and_api_data(db_data, api_data)

    return merged_data


def query_kline_with_results(
    code_list: list[str],
    begin_date: int,
    end_date: int,
    interval: int,
    begin_time: int = None,
    end_time: int = None,
) -> KlineQueryResult:
    """使用结果封装类型查询K线数据.

    Args:
        code_list: 证券代码列表
        begin_date: 开始日期 (YYYYMMDD 格式整数)
        end_date: 结束日期 (YYYYMMDD 格式整数)
        interval: 数据周期对应的 SDK 整数值（调用 `ad.query_kline` 时仍使用 `period` 参数）
        begin_time: 开始时间 (HHMMSSNNN 格式整数)
        end_time: 结束时间 (HHMMSSNNN 格式整数)

    Returns:
        KlineQueryResult: 封装的查询结果
    """
    # 调用原始API获取数据
    try:
        kline_dict = amazing_data_client.query_kline(
            code_list=code_list,
            begin_date=begin_date,
            end_date=end_date,
            period=interval,  # 这里只保留 AmazingData SDK 所需的参数名
            begin_time=begin_time,
            end_time=end_time,
        )
    except TypeError as e:
        if "'NoneType' object cannot be interpreted as an integer" in str(e):
            # 这是AmazingData SDK的一个已知bug
            # 将其作为SDK_BUG_ERROR处理
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
        else:
            raise
    except Exception as e:
        logger.error(f"API调用失败: {e}")
        # 构建错误结果
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

    # 构建结果对象
    results = {}

    # 处理成功的结果
    for code in code_list:
        if code in kline_dict:
            data = kline_dict[code]
            if data is not None and not data.empty:
                # 成功情况
                results[code] = KlineItemResult.from_success(
                    code=code, data=data, interval=interval  # 结果对象统一使用 interval 命名
                )
            else:
                # API返回None或空DataFrame，表示无数据
                error = KlineError(
                    error_code=KlineErrorCode.NO_DATA_FOUND,
                    message=f"代码 {code} 在指定日期范围内无数据",
                    affected_codes=[code],
                )
                results[code] = KlineItemResult.from_error(
                    code=code, error=error, interval=interval
                )
        else:
            # 代码不在返回字典中，可能是无效代码
            error = KlineError(
                error_code=KlineErrorCode.INVALID_CODE,
                message=f"证券代码无效: {code}",
                affected_codes=[code],
            )
            results[code] = KlineItemResult.from_error(
                code=code, error=error, interval=interval
            )

    return KlineQueryResult(results=results)
