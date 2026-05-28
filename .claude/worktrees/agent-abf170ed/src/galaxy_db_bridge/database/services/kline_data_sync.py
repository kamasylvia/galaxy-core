"""K 线数据同步服务.

专门用于 K 线数据的同步服务，从 API 获取数据并存储到数据库。
"""

import logging
from datetime import date, datetime, timedelta

import pandas as pd

from galaxy_db_bridge.amazing_data.api.client import amazing_data_client
from galaxy_db_bridge.database.services.kline import kline_service
from galaxy_db_bridge.database.services.kline_completeness_checker import (
    CompletenessResult,
    kline_completeness_checker,
)
from galaxy_db_bridge.shared_kernel.utils.time_parser import (
    datetime_to_int,
    parse_date_to_datetime,
)
from galaxy_db_bridge.database.services.trading_calendar import trading_calendar_service
from galaxy_db_bridge.shared_kernel.utils.symbol_validator import infer_security_type
from galaxy_db_bridge.shared_kernel.enums.security_type import SecurityType

logger = logging.getLogger(__name__)


class KlineDataSyncService:
    """K 线数据同步服务."""

    def __init__(self):
        """初始化 K 线数据同步服务."""
        self.kline_service = kline_service

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

    def _get_market_from_symbol(self, symbol: str) -> str:
        """根据证券代码获取市场代码."""
        if symbol.endswith(".SH"):
            return "SSE"
        elif symbol.endswith(".SZ"):
            return "SZSE"
        elif symbol.endswith(".BJ"):
            return "BSE"
        else:
            # 默认返回SSE，可根据需要调整
            return "SSE"

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

            logger.info(f"{symbol}: 完整性检查完成 - {completeness_result}")
            return completeness_result

        except Exception as e:
            logger.error(f"{symbol}: 完整性检查失败 - {e}")
            return self._fallback_completeness_check(
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

        market = self._get_market_from_symbol(symbol)
        trading_days = trading_calendar_service.get_trading_days(
            start_date, end_date, market=market
        )

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
        interval_value: str,
    ) -> int:
        """同步单个证券的 K 线数据.

        Args:
            symbol: 证券代码
            interval: K 线周期
            start_date: 开始日期字符串
            end_date: 结束日期字符串
            interval_value: 数据周期对应的 SDK 整数值

        Returns:
            同步的数据条数
        """
        total_synced = 0

        try:
            logger.info(f"{symbol}: 开始同步 K 线数据...")

            start_dt = parse_date_to_datetime(start_date, interval)
            end_dt = parse_date_to_datetime(end_date, interval)

            # 需要将 datetime 对象转换为 date 对象
            start_date_obj = (
                start_dt.date() if isinstance(start_dt, datetime) else start_dt
            )
            end_date_obj = end_dt.date() if isinstance(end_dt, datetime) else end_dt

            logger.info(f"{symbol}: 请求日期范围 {start_date_obj} ~ {end_date_obj}")

            completeness_result = self._check_data_completeness(
                symbol=symbol,
                interval=interval,
                start_date=start_date_obj,
                end_date=end_date_obj,
            )

            if completeness_result.is_complete:
                logger.info(f"{symbol}: 数据已完整，无需获取新数据")
                return 0

            if not completeness_result.missing_ranges:
                logger.info(f"{symbol}: 未识别到需要同步的缺失区间")
                return 0

            logger.info(
                f"{symbol}: 需要补充 {completeness_result.missing_count} 个数据点，"
                f"涉及 {len(completeness_result.missing_ranges)} 个缺失区间"
            )

            for missing_start, missing_end in completeness_result.missing_ranges:
                range_start_int = datetime_to_int(missing_start)
                range_end_int = datetime_to_int(missing_end)

                logger.info(
                    f"{symbol}: 正在获取 {range_start_int} ~ {range_end_int} 的数据..."
                )

                try:
                    kline_dict = amazing_data_client.query_kline(
                        code_list=[symbol],
                        begin_date=range_start_int,
                        end_date=range_end_int,
                        interval=interval_value,
                    )
                except TypeError as e:
                    if "'NoneType' object cannot be interpreted as an integer" in str(e):
                        logger.warning(f"{symbol}: API 调用遇到已知 SDK 错误: {e}")
                        kline_dict = {symbol: None}
                    else:
                        raise
                except Exception as e:
                    logger.error(f"{symbol}: API 调用失败: {e}")
                    raise

                if symbol in kline_dict:
                    df = kline_dict[symbol]
                    if df is not None and not df.empty:
                        inferred_security_type = infer_security_type(symbol)

                        if interval.lower() == "year":
                            if inferred_security_type not in [
                                SecurityType.SH_ETF.value,
                                SecurityType.SZ_ETF.value,
                                SecurityType.EXTRA_ETF.value,
                            ]:
                                logger.warning(
                                    f"{symbol}: 年线数据同步中发现非 ETF 代码（推断类型为 {inferred_security_type}），跳过保存"
                                )
                                return 0

                        saved_count = self.save_kline_data(
                            code=symbol,
                            df=df,
                            interval=interval,
                            security_type=inferred_security_type or "stock",
                        )
                        total_synced += saved_count
                        logger.info(f"{symbol}: 获取并保存了 {saved_count} 条数据")
                    else:
                        logger.error(f"{symbol}: API 返回空数据，可能是代码不合法或无数据")
                        raise Exception(
                            f"API 返回空数据，可能是代码 {symbol} 不合法或在指定日期范围内无数据"
                        )
                else:
                    logger.warning(
                        f"{symbol}: 未找到 {range_start_int} ~ {range_end_int} 的数据"
                    )

        except Exception as e:
            logger.error(f"{symbol}: 处理失败 - {e}")
            import traceback

            traceback.print_exc()
            raise

        return total_synced


# 全局 K 线数据同步服务实例
kline_data_sync_service = KlineDataSyncService()
