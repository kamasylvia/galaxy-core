"""K 线数据同步服务.

专门用于 K 线数据的同步服务，从 API 获取数据并存储到数据库。
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd

from galaxy_db_sync.amazing_data.api.client import amazing_data_client
from galaxy_db_sync.database.services.kline import kline_service
from galaxy_db_sync.database.services.empty_query import empty_query_service
from galaxy_db_sync.database.services.kline_completeness_checker import (
    CompletenessResult,
    kline_completeness_checker,
)
from galaxy_db_sync.database.services.missing_data_tracker import missing_data_tracker
from galaxy_db_sync.shared_kernel.utils.time_parser import (
    datetime_to_int,
    parse_date_to_datetime,
)
from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service
from galaxy_db_sync.shared_kernel.utils import infer_security_type
from galaxy_db_sync.shared_kernel.enums.security_type import SecurityType
from galaxy_db_sync.shared_kernel.utils.interval_boundary_checker import IntervalBoundaryChecker
from galaxy_db_sync.shared_kernel.exceptions import SDKError

logger = logging.getLogger(__name__)


class KlineDataSyncService:
    """K 线数据同步服务."""

    def __init__(self):
        """初始化 K 线数据同步服务."""
        self.kline_service = kline_service
        self._interval_boundary_checker = IntervalBoundaryChecker()

    @property
    def interval_boundary_checker(self) -> IntervalBoundaryChecker:
        """获取周期边界检查器实例"""
        return self._interval_boundary_checker

    def _merge_small_gaps(
        self,
        missing_ranges: list[tuple[date, date]],
        max_gap_days: int = 5,
        min_ranges_to_trigger: int = 10,
    ) -> list[tuple[date, date]]:
        """合并间隔较小的缺失区间，减少 API 调用次数.

        当缺失区间数量超过 min_ranges_to_trigger 时，将间隔不超过
        max_gap_days 的相邻区间合并为一个大区间。
        重复数据通过 UPSERT 自动去重，不会重复存储。

        Args:
            missing_ranges: 原始缺失区间列表
            max_gap_days: 允许合并的最大间隔天数
            min_ranges_to_trigger: 触发合并的最小区间数量

        Returns:
            合并后的缺失区间列表
        """
        if len(missing_ranges) <= min_ranges_to_trigger:
            return missing_ranges

        sorted_ranges = sorted(missing_ranges, key=lambda x: x[0])
        merged = [sorted_ranges[0]]

        for current_start, current_end in sorted_ranges[1:]:
            last_start, last_end = merged[-1]
            gap = (current_start - last_end).days

            if gap <= max_gap_days:
                merged[-1] = (last_start, max(last_end, current_end))
            else:
                merged.append((current_start, current_end))

        return merged

    def _cluster_range_groups(
        self,
        range_groups: dict[tuple[int, int], list[str]],
        max_gap_days: int = 30,
        max_range_days: int = 180,
    ) -> dict[tuple[int, int], list[str]]:
        """跨证券合并重叠或相近的日期区间组，减少 API 调用次数.

        不同证券的缺失区间往往高度重叠（如上市初期的共同缺失）。
        将 gap 不超过 max_gap_days 的区间组合并为更大的组，
        同时限制每个合并后区间的最大长度不超过 max_range_days。
        重复数据通过 UPSERT 自动去重。

        Args:
            range_groups: {(start_ymd, end_ymd): [symbols, ...]}
            max_gap_days: 允许合并的最大间隔天数
            max_range_days: 每个合并后区间的最大长度（天）

        Returns:
            合并后的区间组
        """
        if not range_groups or len(range_groups) <= 1:
            return range_groups

        # 解析为 (start_dt, end_dt, symbols_set)
        items = []
        for (start_int, end_int), symbols in range_groups.items():
            start_dt = datetime.strptime(str(start_int), "%Y%m%d").date()
            end_dt = datetime.strptime(str(end_int), "%Y%m%d").date()
            items.append((start_dt, end_dt, set(symbols)))

        # 按开始日期排序
        items.sort(key=lambda x: x[0])

        merged: list[tuple[date, date, set[str]]] = []
        cur_start, cur_end, cur_symbols = items[0]

        for start, end, symbols in items[1:]:
            gap = (start - cur_end).days
            potential_length = (max(cur_end, end) - cur_start).days

            # 如果新区间完全被当前区间包含（或完全相同），直接合并 symbol
            if start >= cur_start and end <= cur_end:
                cur_symbols.update(symbols)
            # 合并条件：gap 在允许范围内，且合并后总长度不超过限制
            elif gap <= max_gap_days and potential_length <= max_range_days:
                cur_end = max(cur_end, end)
                cur_symbols.update(symbols)
            else:
                merged.append((cur_start, cur_end, cur_symbols))
                cur_start, cur_end, cur_symbols = start, end, symbols

        merged.append((cur_start, cur_end, cur_symbols))

        # 转换回 YYYYMMDD 格式
        result = {}
        for start, end, symbols in merged:
            key = (int(start.strftime("%Y%m%d")), int(end.strftime("%Y%m%d")))
            result[key] = sorted(symbols)

        if len(result) < len(range_groups):
            logger.debug(
                f"全局区间合并: {len(range_groups)} 组 -> {len(result)} 组"
            )
        return result

    def get_kline_data_range(
        self,
        code: str,
        interval: str,
    ):
        """查询数据库中已有 K 线数据的日期范围."""
        return self.kline_service.get_data_range_for_symbol(code, interval)

    def save_kline_data(
        self,
        code: str,
        df: pd.DataFrame,
        interval: str,
        security_type: str = "stock",
    ) -> int:
        """将 K 线数据保存到数据库."""
        return self.kline_service.save_kline_to_db(code, df, interval, security_type)

    def _check_data_completeness(
        self,
        symbol: str,
        interval: str,
        start_date: date,
        end_date: date,
    ) -> CompletenessResult:
        """检查数据完整性并返回统一结果对象."""
        try:
            completeness_result = kline_completeness_checker.check(
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
            )

            logger.debug(f"{symbol}: 完整性检查完成 - {completeness_result}")
            return completeness_result

        except Exception as e:
            logger.error(f"{symbol}: 完整性检查失败 - {e}")
            return self._fallback_completeness_check(
                symbol, interval, start_date, end_date
            )

    async def _check_data_completeness_async(
        self,
        symbol: str,
        interval: str,
        start_date: date,
        end_date: date,
    ) -> CompletenessResult:
        """检查数据完整性（异步版本）."""
        try:
            completeness_result = await kline_completeness_checker.check_async(
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
            )

            logger.debug(f"{symbol}: 完整性检查完成 - {completeness_result}")
            return completeness_result

        except Exception as e:
            logger.error(f"{symbol}: 完整性检查失败 - {e}")
            return await self._fallback_completeness_check_async(
                symbol, interval, start_date, end_date
            )

    def _fallback_completeness_check(
        self,
        symbol: str,
        interval: str,
        start_date: date,
        end_date: date,
    ) -> CompletenessResult:
        """回退的完整性检查方法."""
        logger.warning(f"{symbol}: 使用回退方法检查完整性")

        trading_days = trading_calendar_service.get_trading_days(start_date, end_date)

        db_data = kline_service.query_kline_from_db(
            symbols=[symbol],
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            interval=interval,
        )

        existing_dates = set()
        if symbol in db_data and not db_data[symbol].empty:
            existing_dates = set(db_data[symbol].index.date)

        missing_dates = sorted(day for day in trading_days if day not in existing_dates)
        missing_ranges = self._merge_dates_to_ranges(missing_dates)
        total_count = len(trading_days)
        missing_count = len(missing_dates)
        coverage_ratio = (
            (total_count - missing_count) / total_count if total_count > 0 else 1.0
        )

        return CompletenessResult(
            is_complete=missing_count == 0,
            missing_count=missing_count,
            total_count=total_count,
            coverage_ratio=coverage_ratio,
            missing_ranges=missing_ranges,
            check_method="fallback_trading_day",
        )

    async def _fallback_completeness_check_async(
        self,
        symbol: str,
        interval: str,
        start_date: date,
        end_date: date,
    ) -> CompletenessResult:
        """回退的完整性检查方法（异步版本）."""
        logger.warning(f"{symbol}: 使用回退方法检查完整性 [async]")

        trading_days = await trading_calendar_service.get_trading_days_async(start_date, end_date)

        db_data = await kline_service.query_kline_from_db(
            symbols=[symbol],
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            interval=interval,
        )

        existing_dates = set()
        if symbol in db_data and not db_data[symbol].empty:
            existing_dates = set(db_data[symbol].index.date)

        missing_dates = sorted(day for day in trading_days if day not in existing_dates)
        missing_ranges = self._merge_dates_to_ranges(missing_dates)
        total_count = len(trading_days)
        missing_count = len(missing_dates)
        coverage_ratio = (
            (total_count - missing_count) / total_count if total_count > 0 else 1.0
        )

        return CompletenessResult(
            is_complete=missing_count == 0,
            missing_count=missing_count,
            total_count=total_count,
            coverage_ratio=coverage_ratio,
            missing_ranges=missing_ranges,
            check_method="fallback_trading_day_async",
        )

    def _merge_dates_to_ranges(
        self,
        dates: list[date],
    ) -> list[tuple[date, date]]:
        """将日期列表合并为连续区间."""
        if not dates:
            return []

        ranges: list[tuple[date, date]] = []
        range_start = dates[0]
        range_end = dates[0]

        for current in dates[1:]:
            if current > range_end + timedelta(days=1):
                ranges.append((range_start, range_end))
                range_start = current
            range_end = current

        ranges.append((range_start, range_end))
        return ranges

    def sync_kline_data(
        self,
        symbol: str,
        interval: str,
        start_date: str | None,
        end_date: str | None,
    ) -> int:
        """同步单个证券的 K 线数据.

        Args:
            symbol: 证券代码
            interval: K 线周期
            start_date: 开始日期字符串
            end_date: 结束日期字符串

        Returns:
            同步的数据条数
        """
        total_synced = 0

        try:
            logger.debug(f"{symbol}: 开始同步 K 线数据...")

            start_dt = parse_date_to_datetime(start_date, interval)
            end_dt = parse_date_to_datetime(end_date, interval)

            # 需要将 datetime 对象转换为 date 对象
            start_date_obj = (
                start_dt.date() if isinstance(start_dt, datetime) else start_dt
            )
            end_date_obj = end_dt.date() if isinstance(end_dt, datetime) else end_dt

            # 对于长周期，自动调整 end_date 到已结束周期的边界
            if self._interval_boundary_checker.is_long_interval(interval):
                adjusted_end = self._interval_boundary_checker.get_last_complete_interval_end(
                    interval, end_date_obj
                )
                if adjusted_end < end_date_obj:
                    logger.debug(
                        f"长周期 {interval} 调整 end_date: "
                        f"{end_date_obj.strftime('%Y%m%d')} -> {adjusted_end.strftime('%Y%m%d')}"
                    )
                    end_date_obj = adjusted_end

            logger.debug(f"{symbol}: 请求日期范围 {start_date_obj} ~ {end_date_obj}")

            completeness_result = self._check_data_completeness(
                symbol=symbol,
                interval=interval,
                start_date=start_date_obj,
                end_date=end_date_obj,
            )

            if completeness_result.is_complete:
                logger.debug(f"{symbol}: 数据已完整，无需获取新数据")
                return 0

            if not completeness_result.missing_ranges:
                logger.debug(f"{symbol}: 未识别到需要同步的缺失区间")
                return 0

            missing_ranges_to_query = [
                (range_start, range_end)
                for range_start, range_end in completeness_result.missing_ranges
                if not empty_query_service.is_confirmed_empty(
                    symbol, interval, range_start, range_end
                )
            ]

            if not missing_ranges_to_query:
                logger.debug(f"{symbol}: 所有缺失区间都已被确认为空数据，跳过 API 查询")
                return 0

            logger.info(
                f"开始同步K线数据: {symbol} {interval} "
                f"{start_date_obj.strftime('%Y%m%d')} - {end_date_obj.strftime('%Y%m%d')}"
            )

            for range_start, range_end in missing_ranges_to_query:
                range_start_int = datetime_to_int(range_start)
                range_end_int = datetime_to_int(range_end)

                logger.debug(
                    f"{symbol}: 正在获取 {range_start_int} ~ {range_end_int} 的数据..."
                )

                try:
                    kline_dict = amazing_data_client.get_kline(
                        code_list=[symbol],
                        begin_date=range_start_int,
                        end_date=range_end_int,
                        interval=interval,
                    )
                except TypeError as e:
                    if "'NoneType' object cannot be interpreted as an integer" in str(e):
                        logger.warning(
                            f"{symbol}: API 调用遇到已知 SDK 错误，跳过区间 "
                            f"{range_start_int} ~ {range_end_int} 且不写入空结果缓存: {e}"
                        )
                        continue
                    raise
                except SDKError as e:
                    logger.error(f"{symbol}: SDK 错误: {e.message}")
                    raise
                except Exception as e:
                    logger.error(f"{symbol}: API 调用失败: {type(e).__name__}: {e}")
                    raise

                if symbol in kline_dict:
                    df = kline_dict[symbol]
                    if df is not None and not df.empty:
                        inferred_security_type = infer_security_type(symbol)

                        if interval.lower() == "year" and inferred_security_type not in [
                            SecurityType.SH_ETF.value,
                            SecurityType.SZ_ETF.value,
                            SecurityType.EXTRA_ETF.value,
                        ]:
                            logger.warning(
                                f"{symbol}: 年线数据同步中发现非 ETF 代码（推断类型为 {inferred_security_type}），跳过保存"
                            )
                            continue

                        saved_count = self.save_kline_data(
                            code=symbol,
                            df=df,
                            interval=interval,
                            security_type=inferred_security_type or "stock",
                        )
                        total_synced += saved_count
                        logger.debug(f"{symbol}: 获取并保存了 {saved_count} 条数据")
                    else:
                        logger.warning(
                            f"{symbol}: API 返回空数据，跳过区间 "
                            f"{range_start_int} ~ {range_end_int} 并记录到空结果缓存"
                        )
                        empty_query_service.record_empty_result(
                            symbol, interval, range_start, range_end
                        )
                else:
                    logger.warning(
                        f"{symbol}: 未找到 {range_start_int} ~ {range_end_int} 的数据，"
                        f"记录到空结果缓存"
                    )
                    empty_query_service.record_empty_result(
                        symbol, interval, range_start, range_end
                    )

        except Exception as e:
            logger.error(f"{symbol}: 处理失败 - {e}")
            import traceback

            traceback.print_exc()
            raise

        return total_synced

    async def sync_kline_data_async(
        self,
        symbol: str,
        interval: str,
        start_date: str | None,
        end_date: str | None,
    ) -> int:
        """同步单个证券的 K 线数据（异步版本）.

        Args:
            symbol: 证券代码
            interval: K 线周期
            start_date: 开始日期字符串
            end_date: 结束日期字符串

        Returns:
            同步的数据条数
        """
        total_synced = 0

        try:
            logger.debug(f"{symbol}: 开始同步 K 线数据 [async]...")

            start_dt = parse_date_to_datetime(start_date, interval)
            end_dt = parse_date_to_datetime(end_date, interval)

            start_date_obj = (
                start_dt.date() if isinstance(start_dt, datetime) else start_dt
            )
            end_date_obj = end_dt.date() if isinstance(end_dt, datetime) else end_dt

            # 对于长周期，自动调整 end_date 到已结束周期的边界
            if self._interval_boundary_checker.is_long_interval(interval):
                adjusted_end = await asyncio.to_thread(
                    self._interval_boundary_checker.get_last_complete_interval_end,
                    interval, end_date_obj
                )
                if adjusted_end < end_date_obj:
                    logger.debug(
                        f"长周期 {interval} 调整 end_date: "
                        f"{end_date_obj.strftime('%Y%m%d')} -> {adjusted_end.strftime('%Y%m%d')}"
                    )
                    end_date_obj = adjusted_end

            logger.debug(f"{symbol}: 请求日期范围 {start_date_obj} ~ {end_date_obj}")

            completeness_result = await self._check_data_completeness_async(
                symbol=symbol,
                interval=interval,
                start_date=start_date_obj,
                end_date=end_date_obj,
            )

            if completeness_result.is_complete:
                logger.debug(f"{symbol}: 数据已完整，无需获取新数据")
                return 0

            if not completeness_result.missing_ranges:
                logger.debug(f"{symbol}: 未识别到需要同步的缺失区间")
                return 0

            # 异步检查缺失区间是否已确认为空
            missing_ranges_to_query = []
            for range_start, range_end in completeness_result.missing_ranges:
                if not await empty_query_service.is_confirmed_empty_async(
                    symbol, interval, range_start, range_end
                ):
                    missing_ranges_to_query.append((range_start, range_end))

            if not missing_ranges_to_query:
                logger.debug(f"{symbol}: 所有缺失区间都已被确认为空数据，跳过 API 查询")
                return 0

            logger.info(
                f"开始同步K线数据: {symbol} {interval} "
                f"{start_date_obj.strftime('%Y%m%d')} - {end_date_obj.strftime('%Y%m%d')}"
            )

            for range_start, range_end in missing_ranges_to_query:
                range_start_int = datetime_to_int(range_start)
                range_end_int = datetime_to_int(range_end)

                logger.debug(
                    f"{symbol}: 正在获取 {range_start_int} ~ {range_end_int} 的数据..."
                )

                try:
                    # SDK is sync, use asyncio.to_thread
                    kline_dict = await asyncio.to_thread(
                        amazing_data_client.get_kline,
                        code_list=[symbol],
                        begin_date=range_start_int,
                        end_date=range_end_int,
                        interval=interval,
                    )
                except TypeError as e:
                    if "'NoneType' object cannot be interpreted as an integer" in str(e):
                        logger.warning(
                            f"{symbol}: API 调用遇到已知 SDK 错误，跳过区间 "
                            f"{range_start_int} ~ {range_end_int} 且不写入空结果缓存: {e}"
                        )
                        continue
                    raise
                except SDKError as e:
                    logger.error(f"{symbol}: SDK 错误: {e.message}")
                    raise
                except Exception as e:
                    logger.error(f"{symbol}: API 调用失败: {type(e).__name__}: {e}")
                    raise

                if symbol in kline_dict:
                    df = kline_dict[symbol]
                    if df is not None and not df.empty:
                        inferred_security_type = infer_security_type(symbol)

                        if interval.lower() == "year" and inferred_security_type not in [
                            SecurityType.SH_ETF.value,
                            SecurityType.SZ_ETF.value,
                            SecurityType.EXTRA_ETF.value,
                        ]:
                            logger.warning(
                                f"{symbol}: 年线数据同步中发现非 ETF 代码（推断类型为 {inferred_security_type}），跳过保存"
                            )
                            continue

                        saved_count = await self.kline_service.save_kline_to_db(
                            symbol=symbol,
                            df=df,
                            interval=interval,
                            security_type=inferred_security_type or "stock",
                        )
                        total_synced += saved_count
                        logger.debug(f"{symbol}: 获取并保存了 {saved_count} 条数据")
                    else:
                        logger.warning(
                            f"{symbol}: API 返回空数据，跳过区间 "
                            f"{range_start_int} ~ {range_end_int} 并记录到空结果缓存"
                        )
                        await empty_query_service.record_empty_result_async(
                            symbol, interval, range_start, range_end
                        )
                else:
                    logger.warning(
                        f"{symbol}: 未找到 {range_start_int} ~ {range_end_int} 的数据，"
                        f"记录到空结果缓存"
                    )
                    await empty_query_service.record_empty_result_async(
                        symbol, interval, range_start, range_end
                    )

        except Exception as e:
            logger.error(f"{symbol}: 处理失败 - {e}")
            import traceback

            traceback.print_exc()
            raise

        return total_synced


    def batch_sync_kline_data(
        self,
        symbols: List[str],
        interval: str,
        start_date: str,
        end_date: str,
        completeness_results: dict = None,
        batch_size: int = 500,
    ) -> "BatchSyncResult":
        """批量同步 K 线数据（按日期缺失区间分批）.

        Args:
            symbols: 证券代码列表
            interval: K线周期
            start_date: 开始日期 (YYYYMMDD 格式)
            end_date: 结束日期 (YYYYMMDD 格式)
            completeness_results: 完整性检查结果，用于按缺失区间分批
            batch_size: 每批处理的最大证券数量（在单个日期区间内）

        Returns:
            BatchSyncResult: 批量同步结果
        """
        # 如果没有提供完整性结果，或没有缺失区间，按原来的方式处理
        if not completeness_results:
            return self._batch_sync_by_symbol_count(
                symbols, interval, start_date, end_date, batch_size
            )

        # 按日期缺失区间分组（使用统一的完整日期范围）
        range_groups = self._group_by_missing_ranges(
            {s: completeness_results[s] for s in symbols if s in completeness_results},
            interval,
            full_start=start_date,
            full_end=end_date,
        )

        if not range_groups:
            logger.info("没有需要同步的日期区间")
            return BatchSyncResult(
                success_count=len(symbols),
                synced_records=0,
                failed_codes=[],
            )

        total_saved = 0
        success_count = 0
        failed_codes = []
        api_call_count = 0

        # 按日期区间分批处理
        for (begin_int, end_int), symbols_in_range in range_groups.items():
            logger.debug(
                f"同步区间 {begin_int} ~ {end_int}: {len(symbols_in_range)} 个证券"
            )

            # 解析日期区间
            start_dt = datetime.strptime(str(begin_int), "%Y%m%d").date()
            end_dt = datetime.strptime(str(end_int), "%Y%m%d").date()

            # 在单个日期区间内，再按 batch_size 分批处理证券
            for i in range(0, len(symbols_in_range), batch_size):
                batch = symbols_in_range[i : i + batch_size]

                try:
                    # 批量 API 查询
                    kline_dict = amazing_data_client.get_kline(
                        code_list=batch,
                        begin_date=begin_int,
                        end_date=end_int,
                        interval=interval,
                    )
                    api_call_count += 1
                except TypeError as e:
                    if "'NoneType' object cannot be interpreted as an integer" in str(e):
                        logger.warning(
                            f"批次 API 调用遇到已知 SDK 错误，跳过区间 {begin_int} ~ {end_int} 且不写入空结果缓存: {e}"
                        )
                        continue
                    raise

                try:
                    # 批量保存（async 方法在 sync 函数中需用 asyncio.run 包装）
                    import asyncio
                    saved_count = asyncio.run(self.kline_service.batch_save_kline_to_db(kline_dict, interval))
                    total_saved += saved_count

                    # 收集空结果和确认记录，用于批量处理
                    empty_records: list[tuple[str, date, date]] = []
                    confirm_records: list[tuple[str, date, date, Optional[str]]] = []

                    # 统计成功/失败
                    for symbol in batch:
                        if (
                            symbol in kline_dict
                            and kline_dict[symbol] is not None
                            and not kline_dict[symbol].empty
                        ):
                            success_count += 1
                            # 检查 API 返回的数据是否覆盖请求范围
                            # 对于新上市 ETF，上市前的日期不会有数据，需要确认缺失
                            df = kline_dict[symbol]
                            if len(df) > 0:
                                from datetime import timedelta as td
                                # API 返回的 DataFrame 使用 RangeIndex，日期在 kline_time 列
                                min_time = df['kline_time'].min()
                                max_time = df['kline_time'].max()
                                min_date = min_time.date() if isinstance(min_time, datetime) else min_time
                                max_date = max_time.date() if isinstance(max_time, datetime) else max_time

                                # 如果返回数据的最早日期晚于请求的开始日期
                                # 说明上市前的日期没有数据，确认缺失
                                if min_date > start_dt:
                                    confirm_records.append(
                                        (symbol, start_dt, min_date - td(days=1),
                                         f"Data starts from {min_date}, likely pre-listing period")
                                    )

                                # 如果返回数据的最晚日期早于请求的结束日期
                                # 说明结束后的日期没有数据，确认缺失
                                if max_date < end_dt:
                                    confirm_records.append(
                                        (symbol, max_date + td(days=1), end_dt,
                                         f"Data ends at {max_date}, likely post-listing or future")
                                    )
                        else:
                            # 如果 API 返回空，也认为是成功的（标记为已确认无数据）
                            if symbol in kline_dict:
                                success_count += 1
                                empty_records.append((symbol, start_dt, end_dt))
                                confirm_records.append(
                                    (symbol, start_dt, end_dt, "API returned empty DataFrame")
                                )
                            else:
                                failed_codes.append(symbol)

                    # 批量写入空查询缓存和确认记录
                    if empty_records:
                        empty_query_service.batch_record_empty_results(interval, empty_records)
                    if confirm_records:
                        missing_data_tracker.batch_confirm_missing_as_api_empty(interval, confirm_records)

                except Exception as e:
                    logger.error(f"  批次处理失败: {type(e).__name__}: {e}")
                    failed_codes.extend(batch)

        # 整合显示单次同步结果
        if total_saved > 0 or api_call_count > 0:
            logger.info(
                f"同步: {api_call_count} 次API, {total_saved} 条记录, "
                f"成功 {success_count}/{len(symbols)}"
            )

        if failed_codes:
            logger.warning(f"失败: {failed_codes}")

        return BatchSyncResult(
            success_count=success_count,
            synced_records=total_saved,
            failed_codes=failed_codes,
        )

    def _group_by_missing_ranges(
        self,
        completeness_results: dict,
        interval: str,
        full_start: str | None = None,
        full_end: str | None = None,
    ) -> dict[tuple[int, int], list[str]]:
        """按精确缺失区间对 symbol 进行分组.

        跳过已确认缺失的范围（API 返回空的，如停牌期间）。
        """
        from collections import defaultdict

        range_groups: dict[tuple[int, int], list[str]] = defaultdict(list)

        # 收集所有需要检查的区间（合并碎片化小区间以减少 API 调用）
        symbols_and_ranges: list[tuple[str, date, date]] = []
        for symbol, result in completeness_results.items():
            if result.is_complete or not result.missing_ranges:
                continue
            # 激进合并：缺失区间过多时合并为单个大区间
            if len(result.missing_ranges) > 50:
                all_start = min(r[0] for r in result.missing_ranges)
                all_end = max(r[1] for r in result.missing_ranges)
                merged_ranges = [(all_start, all_end)]
                logger.debug(
                    f"{symbol}: 缺失区间 {len(result.missing_ranges)} 个，"
                    f"合并为全量查询 {all_start}~{all_end}"
                )
            else:
                merged_ranges = self._merge_small_gaps(result.missing_ranges)
            for range_start, range_end in merged_ranges:
                symbols_and_ranges.append((symbol, range_start, range_end))

        if not symbols_and_ranges:
            return {}

        # 批量检查空查询缓存
        confirmed_empty = empty_query_service.batch_is_confirmed_empty(
            interval, symbols_and_ranges
        )

        skipped = 0
        for symbol, range_start, range_end in symbols_and_ranges:
            key_str = f"{symbol}|{range_start.isoformat()}|{range_end.isoformat()}"
            if key_str in confirmed_empty:
                skipped += 1
                continue
            key = (int(range_start.strftime("%Y%m%d")), int(range_end.strftime("%Y%m%d")))
            range_groups[key].append(symbol)

        if skipped:
            logger.debug(f"跳过 {skipped} 个已确认缺失区间")

        # 全局合并：跨证券合并重叠或相近的区间组
        range_groups = self._cluster_range_groups(dict(range_groups))

        return range_groups

    async def _group_by_missing_ranges_async(
        self,
        completeness_results: dict,
        interval: str,
        full_start: str | None = None,
        full_end: str | None = None,
    ) -> dict[tuple[int, int], list[str]]:
        """按精确缺失区间对 symbol 进行分组（异步版本）.

        跳过已确认缺失的范围（API 返回空的，如停牌期间）。
        """
        from collections import defaultdict

        range_groups: dict[tuple[int, int], list[str]] = defaultdict(list)

        # 收集所有需要检查的区间（合并碎片化小区间以减少 API 调用）
        symbols_and_ranges: list[tuple[str, date, date]] = []
        for symbol, result in completeness_results.items():
            if result.is_complete or not result.missing_ranges:
                continue
            # 激进合并：缺失区间过多时合并为单个大区间
            if len(result.missing_ranges) > 50:
                all_start = min(r[0] for r in result.missing_ranges)
                all_end = max(r[1] for r in result.missing_ranges)
                merged_ranges = [(all_start, all_end)]
                logger.debug(
                    f"{symbol}: 缺失区间 {len(result.missing_ranges)} 个，"
                    f"合并为全量查询 {all_start}~{all_end}"
                )
            else:
                merged_ranges = self._merge_small_gaps(result.missing_ranges)
            for range_start, range_end in merged_ranges:
                symbols_and_ranges.append((symbol, range_start, range_end))

        if not symbols_and_ranges:
            return {}

        # 批量检查空查询缓存（单次数据库查询）
        confirmed_empty = await empty_query_service.batch_is_confirmed_empty_async(
            interval, symbols_and_ranges
        )

        skipped = 0
        for symbol, range_start, range_end in symbols_and_ranges:
            key_str = f"{symbol}|{range_start.isoformat()}|{range_end.isoformat()}"
            if key_str in confirmed_empty:
                skipped += 1
                continue
            key = (int(range_start.strftime("%Y%m%d")), int(range_end.strftime("%Y%m%d")))
            range_groups[key].append(symbol)

        if skipped:
            logger.debug(f"跳过 {skipped} 个已确认缺失区间")

        # 全局合并：跨证券合并重叠或相近的区间组
        range_groups = self._cluster_range_groups(dict(range_groups))

        return range_groups

    def _batch_sync_by_symbol_count(
        self,
        symbols: List[str],
        interval: str,
        start_date: str,
        end_date: str,
        batch_size: int = 500,
    ) -> "BatchSyncResult":
        """按证券数量分批同步（回退方案）.

        Args:
            symbols: 证券代码列表
            interval: K线周期
            start_date: 开始日期 (YYYYMMDD 格式)
            end_date: 结束日期 (YYYYMMDD 格式)
            batch_size: 每批处理的证券数量

        Returns:
            BatchSyncResult: 批量同步结果
        """
        total_saved = 0
        success_count = 0
        failed_codes = []

        # 确保日期是整数格式 (YYYYMMDD)
        try:
            start_int = int(start_date) if start_date else None
            end_int = int(end_date) if end_date else None

            # 处理年份格式 (如 2025 -> 20250101)
            if start_int and len(str(start_int)) == 4:
                start_int = start_int * 10000 + 101
            if end_int and len(str(end_int)) == 4:
                end_int = end_int * 10000 + 1231

        except ValueError:
            from galaxy_db_sync.shared_kernel.utils.time_parser import parse_date_to_datetime
            start_dt = parse_date_to_datetime(start_date, interval)
            end_dt = parse_date_to_datetime(end_date, interval)
            start_int = int(start_dt.strftime('%Y%m%d')) if isinstance(start_dt, datetime) else int(start_dt)
            end_int = int(end_dt.strftime('%Y%m%d')) if isinstance(end_dt, datetime) else int(end_dt)

        # 按证券数量分批处理
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]

            try:
                # 批量 API 查询
                kline_dict = amazing_data_client.get_kline(
                    code_list=batch,
                    begin_date=start_int,
                    end_date=end_int,
                    interval=interval,
                )

                # 批量保存
                saved_count = self.kline_service.batch_save_kline_to_db(kline_dict, interval)
                total_saved += saved_count

                # 统计成功/失败
                for symbol in batch:
                    if (
                        symbol in kline_dict
                        and kline_dict[symbol] is not None
                        and not kline_dict[symbol].empty
                    ):
                        success_count += 1
                    else:
                        failed_codes.append(symbol)

            except Exception as e:
                logger.error(f"批次处理失败: {type(e).__name__}: {e}")
                failed_codes.extend(batch)

        return BatchSyncResult(
            success_count=success_count,
            synced_records=total_saved,
            failed_codes=failed_codes,
        )

    async def batch_sync_kline_data_async(
        self,
        symbols: List[str],
        interval: str,
        start_date: str,
        end_date: str,
        completeness_results: dict = None,
        batch_size: int = 500,
    ) -> "BatchSyncResult":
        """异步批量同步 K 线数据（按日期缺失区间分批）.

        Args:
            symbols: 证券代码列表
            interval: K线周期
            start_date: 开始日期 (YYYYMMDD 格式)
            end_date: 结束日期 (YYYYMMDD 格式)
            completeness_results: 完整性检查结果，用于按缺失区间分批
            batch_size: 每批处理的最大证券数量（在单个日期区间内）

        Returns:
            BatchSyncResult: 批量同步结果
        """
        # 如果没有提供完整性结果，或没有缺失区间，按原来的方式处理
        if not completeness_results:
            return await self._batch_sync_by_symbol_count_async(
                symbols, interval, start_date, end_date, batch_size
            )

        # 异步按日期缺失区间分组（使用统一的完整日期范围）
        range_groups = await self._group_by_missing_ranges_async(
            {s: completeness_results[s] for s in symbols if s in completeness_results},
            interval,
            full_start=start_date,
            full_end=end_date,
        )

        # 统计实际被查询的证券（未被 empty_query 缓存跳过的）
        symbols_queried = set()
        for symbols_in_range in range_groups.values():
            symbols_queried.update(symbols_in_range)
        skipped_by_cache_count = len(symbols) - len(symbols_queried)

        if not range_groups:
            logger.info(
                f"没有需要同步的日期区间（{skipped_by_cache_count} 只证券被空查询缓存跳过）"
            )
            return BatchSyncResult(
                success_count=0,
                synced_records=0,
                failed_codes=[],
                api_data_count=0,
                api_empty_count=0,
                skipped_by_cache_count=skipped_by_cache_count,
                total_symbols=len(symbols),
            )

        total_saved = 0
        api_data_symbols: set[str] = set()
        api_empty_symbols: set[str] = set()
        failed_symbols: set[str] = set()
        api_call_count = 0

        # 按日期区间分批处理
        for (begin_int, end_int), symbols_in_range in range_groups.items():
            logger.debug(
                f"同步区间 {begin_int} ~ {end_int}: {len(symbols_in_range)} 个证券"
            )

            # 解析日期区间
            start_dt = datetime.strptime(str(begin_int), "%Y%m%d").date()
            end_dt = datetime.strptime(str(end_int), "%Y%m%d").date()

            # 在单个日期区间内，再按 batch_size 分批处理证券
            for i in range(0, len(symbols_in_range), batch_size):
                batch = symbols_in_range[i : i + batch_size]

                try:
                    # 批量 API 查询 (SDK is sync, use asyncio.to_thread)
                    kline_dict = await asyncio.to_thread(
                        amazing_data_client.get_kline,
                        code_list=batch,
                        begin_date=begin_int,
                        end_date=end_int,
                        interval=interval,
                    )
                    api_call_count += 1
                except TypeError as e:
                    if "'NoneType' object cannot be interpreted as an integer" in str(e):
                        logger.warning(
                            f"批次 API 调用遇到已知 SDK 错误，跳过区间 {begin_int} ~ {end_int} 且不写入空结果缓存: {e}"
                        )
                        continue
                    raise

                try:
                    # 批量保存 (async)
                    saved_count = await self.kline_service.batch_save_kline_to_db(kline_dict, interval)
                    total_saved += saved_count

                    # 收集空结果和确认记录，用于批量处理
                    empty_records: list[tuple[str, date, date]] = []
                    confirm_records: list[tuple[str, date, date, Optional[str]]] = []

                    # 统计四种状态：真正同步成功 / API返回空 / 失败
                    for symbol in batch:
                        if (
                            symbol in kline_dict
                            and kline_dict[symbol] is not None
                            and not kline_dict[symbol].empty
                        ):
                            api_data_symbols.add(symbol)
                        else:
                            if symbol in kline_dict:
                                api_empty_symbols.add(symbol)
                                empty_records.append((symbol, start_dt, end_dt))
                                confirm_records.append(
                                    (symbol, start_dt, end_dt, "API returned empty DataFrame")
                                )
                            else:
                                failed_symbols.add(symbol)

                    # 批量写入空查询缓存和确认记录
                    if empty_records:
                        await empty_query_service.batch_record_empty_results_async(
                            interval, empty_records
                        )
                    if confirm_records:
                        await missing_data_tracker.batch_confirm_missing_as_api_empty_async(
                            interval, confirm_records
                        )

                except Exception as e:
                    logger.error(f"  批次处理失败: {type(e).__name__}: {e}")
                    failed_symbols.update(batch)

        # 整合显示单次同步结果
        if total_saved > 0 or api_call_count > 0:
            queried = len(api_data_symbols) + len(api_empty_symbols) + len(failed_symbols)
            logger.info(
                f"同步: {api_call_count} 次API, {total_saved} 条记录, "
                f"查询{queried} = 成功{len(api_data_symbols)} + 空{len(api_empty_symbols)} + 失败{len(failed_symbols)}"
            )

        if failed_symbols:
            failed_list = sorted(failed_symbols)
            logger.warning(f"失败: {failed_list[:20]}{'...' if len(failed_list) > 20 else ''}")

        return BatchSyncResult(
            success_count=len(api_data_symbols) + len(api_empty_symbols),
            synced_records=total_saved,
            failed_codes=list(failed_symbols),
            api_data_count=len(api_data_symbols),
            api_empty_count=len(api_empty_symbols),
            skipped_by_cache_count=skipped_by_cache_count,
            total_symbols=len(symbols),
        )

    async def _batch_sync_by_symbol_count_async(
        self,
        symbols: List[str],
        interval: str,
        start_date: str,
        end_date: str,
        batch_size: int = 500,
    ) -> "BatchSyncResult":
        """异步版本：按证券数量分批同步.

        当没有完整性结果时使用此方法。
        """
        total_saved = 0
        success_count = 0
        failed_codes = []

        # 确保日期是整数格式 (YYYYMMDD)
        try:
            start_int = int(start_date) if start_date else None
            end_int = int(end_date) if end_date else None

            # 处理年份格式 (如 2025 -> 20250101)
            if start_int and len(str(start_int)) == 4:
                start_int = start_int * 10000 + 101
            if end_int and len(str(end_int)) == 4:
                end_int = end_int * 10000 + 1231

        except ValueError:
            from galaxy_db_sync.shared_kernel.utils.time_parser import parse_date_to_datetime
            start_dt = parse_date_to_datetime(start_date, interval)
            end_dt = parse_date_to_datetime(end_date, interval)
            start_int = int(start_dt.strftime('%Y%m%d')) if isinstance(start_dt, datetime) else int(start_dt)
            end_int = int(end_dt.strftime('%Y%m%d')) if isinstance(end_dt, datetime) else int(end_dt)

        # 按证券数量分批处理
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]

            try:
                # 批量 API 查询 (SDK is sync, use asyncio.to_thread)
                kline_dict = await asyncio.to_thread(
                    amazing_data_client.get_kline,
                    code_list=batch,
                    begin_date=start_int,
                    end_date=end_int,
                    interval=interval,
                )

                # 批量保存 (async)
                saved_count = await self.kline_service.batch_save_kline_to_db(kline_dict, interval)
                total_saved += saved_count

                # 统计成功/失败
                for symbol in batch:
                    if (
                        symbol in kline_dict
                        and kline_dict[symbol] is not None
                        and not kline_dict[symbol].empty
                    ):
                        success_count += 1
                    else:
                        failed_codes.append(symbol)

            except Exception as e:
                logger.error(f"批次处理失败: {type(e).__name__}: {e}")
                failed_codes.extend(batch)

        return BatchSyncResult(
            success_count=success_count,
            synced_records=total_saved,
            failed_codes=failed_codes,
        )


@dataclass
@dataclass
class BatchSyncResult:
    """批量同步结果."""

    success_count: int
    synced_records: int
    failed_codes: List[str]
    api_data_count: int = 0
    api_empty_count: int = 0
    skipped_by_cache_count: int = 0
    total_symbols: int = 0

    @property
    def failed_count(self) -> int:
        return len(self.failed_codes)

    @property
    def unexpected_missing_count(self) -> int:
        """不符合预期的未同步数量（理论上应为 0）."""
        return (
            self.total_symbols
            - self.success_count
            - self.skipped_by_cache_count
        )


# 全局 K 线数据同步服务实例
kline_data_sync_service = KlineDataSyncService()
