"""K 线数据服务层 (异步版本).

提供 K 线数据的异步数据库操作接口，包括查询、保存等功能。
使用依赖注入模式，不依赖全局 db_manager 单例。
"""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Union

import pandas as pd
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from galaxy_db_sync.database.core.async_connection import AsyncDatabaseManager
from galaxy_db_sync.database.models.kline import INTERVAL_MODEL_MAP

logger = logging.getLogger(__name__)


# ==================== 辅助类和函数 ====================

class KlineDBInterface:
    """K线数据库操作接口，便于测试mock."""

    @staticmethod
    def build_query(table_model, symbols, start_dt=None, end_dt=None):
        """构建查询语句."""
        query = select(table_model).where(table_model.symbol.in_(symbols))

        if start_dt:
            query = query.where(table_model.trade_time >= start_dt)

        if end_dt:
            query = query.where(table_model.trade_time <= end_dt)

        return query

    @staticmethod
    def build_check_query(table_model, symbol, trade_time):
        """构建检查记录存在的查询语句."""
        return select(table_model).where(
            and_(
                table_model.symbol == symbol,
                table_model.trade_time == trade_time,
            )
        )

    @staticmethod
    def build_range_query(table_model, symbol):
        """构建获取数据范围的查询语句."""
        return select(
            func.min(table_model.trade_time), func.max(table_model.trade_time)
        ).where(table_model.symbol == symbol)

    @staticmethod
    def build_missing_dates_query(table_model, symbol, start_dt, end_dt):
        """构建获取缺失日期的查询语句."""
        return (
            select(table_model.trade_time)
            .where(
                and_(
                    table_model.symbol == symbol,
                    table_model.trade_time >= start_dt,
                    table_model.trade_time <= end_dt,
                )
            )
            .order_by(table_model.trade_time)
        )


def parse_date_for_interval(
    date_value: Union[str, int, datetime],
    interval: str,
    is_end: bool = False,
) -> datetime:
    """根据周期解析日期值.

    Args:
        date_value: 日期值（字符串、整数或 datetime）
        interval: K 线周期
        is_end: 是否为结束日期

    Returns:
        datetime 对象
    """
    if isinstance(date_value, datetime):
        return date_value

    if isinstance(date_value, int):
        date_str = str(date_value)
    else:
        date_str = date_value

    interval_lower = interval.lower()

    if interval_lower in ["month", "season", "year"]:
        if len(date_str) >= 6:
            date_part = date_str[:6]
            year = int(date_part[:4])
            month = int(date_part[4:6])

            if is_end:
                # 根据月份确定最后一天
                if month in [1, 3, 5, 7, 8, 10, 12]:
                    day = "31"
                elif month in [4, 6, 9, 11]:
                    day = "30"
                else:  # 2月
                    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                        day = "29"
                    else:
                        day = "28"
                return datetime.strptime(date_part + day, "%Y%m%d")
            else:
                return datetime.strptime(date_part + "01", "%Y%m%d")
        else:
            if is_end:
                return datetime.strptime(date_str[:4] + "1231", "%Y%m%d")
            else:
                return datetime.strptime(date_str[:4] + "0101", "%Y%m%d")
    else:
        # 日线/周线/分钟线等短周期
        base_dt = datetime.strptime(date_str[:8], "%Y%m%d")
        if is_end:
            # 返回当天的最大时间，确保能捕获所有带时间组件的记录
            return datetime.combine(base_dt.date(), datetime.max.time())
        else:
            return base_dt


def parse_trade_time(value, idx=None) -> datetime:
    """解析交易时间值.

    Args:
        value: 时间值（可能是多种类型）
        idx: 备用索引值

    Returns:
        datetime 对象
    """
    if isinstance(value, datetime):
        return value

    if value is None or (isinstance(value, float) and pd.isna(value)):
        # 使用备用索引
        if idx is not None:
            return parse_trade_time(idx)
        raise ValueError("无法解析交易时间")

    if isinstance(value, str):
        try:
            return datetime.strptime(value[:8], "%Y%m%d")
        except ValueError:
            try:
                return datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                pass
    elif isinstance(value, int):
        try:
            return datetime.strptime(str(value)[:8], "%Y%m%d")
        except ValueError:
            pass

    raise ValueError(f"无法解析交易时间: {value}")


def extract_row_values(row: pd.Series) -> dict:
    """从 DataFrame 行提取值.

    Args:
        row: DataFrame 行

    Returns:
        包含 OHLCV 数据的字典
    """
    return {
        'open': float(row.get("open")) if row.get("open") is not None and pd.notna(row.get("open")) else None,
        'high': float(row.get("high")) if row.get("high") is not None and pd.notna(row.get("high")) else None,
        'low': float(row.get("low")) if row.get("low") is not None and pd.notna(row.get("low")) else None,
        'close': float(row.get("close")) if row.get("close") is not None and pd.notna(row.get("close")) else None,
        'volume': int(row.get("volume")) if row.get("volume") is not None and pd.notna(row.get("volume")) else None,
        'amount': float(row.get("amount")) if row.get("amount") is not None and pd.notna(row.get("amount")) else None,
    }


# ==================== 异步查询函数 ====================

async def query_kline_from_db(
    session: AsyncSession,
    symbols: List[str],
    start_date: Optional[Union[str, int, datetime]] = None,
    end_date: Optional[Union[str, int, datetime]] = None,
    interval: str = "day",
    interval_model_map: dict = None,
) -> Dict[str, pd.DataFrame]:
    """从数据库异步查询 K 线数据.

    Args:
        session: AsyncSession 对象
        symbols: 证券代码列表
        start_date: 开始日期
        end_date: 结束日期
        interval: K 线周期
        interval_model_map: 周期到表模型的映射

    Returns:
        以证券代码为键的 K 线数据 DataFrame 字典
    """
    if interval_model_map is None:
        interval_model_map = INTERVAL_MODEL_MAP

    interval_lower = interval.lower()
    if interval_lower not in interval_model_map:
        raise ValueError(f"不支持的周期: {interval}")

    table_model = interval_model_map[interval_lower]

    start_dt = parse_date_for_interval(start_date, interval, is_end=False) if start_date else None
    end_dt = parse_date_for_interval(end_date, interval, is_end=True) if end_date else None

    query = KlineDBInterface.build_query(table_model, symbols, start_dt, end_dt)

    result = await session.execute(query)
    records = result.scalars().all()

    # 按证券代码分组数据
    kline_dict = {}
    for record in records:
        if record.symbol not in kline_dict:
            kline_dict[record.symbol] = []

        kline_dict[record.symbol].append(
            {
                "trade_time": record.trade_time,
                "open": float(record.open) if record.open is not None else None,
                "high": float(record.high) if record.high is not None else None,
                "low": float(record.low) if record.low is not None else None,
                "close": float(record.close) if record.close is not None else None,
                "volume": int(record.volume) if record.volume is not None else None,
                "amount": float(record.amount) if record.amount is not None else None,
            }
        )

    # 确保所有请求的符号都在结果中
    for symbol in symbols:
        if symbol not in kline_dict:
            kline_dict[symbol] = pd.DataFrame(
                columns=["open", "high", "low", "close", "volume", "amount"]
            ).astype(
                {
                    "open": "float64",
                    "high": "float64",
                    "low": "float64",
                    "close": "float64",
                    "volume": "int64",
                    "amount": "float64",
                }
            )

    # 将列表转换为 DataFrame
    for symbol, data_list in kline_dict.items():
        if symbol in [record.symbol for record in records]:
            if data_list:
                df = pd.DataFrame(data_list)
                df.set_index("trade_time", inplace=True)
                df.sort_index(inplace=True)
                kline_dict[symbol] = df

    return kline_dict


async def get_available_intervals_for_symbol(
    session: AsyncSession,
    symbol: str,
    interval_model_map: dict = None,
) -> List[str]:
    """获取指定证券代码在数据库中存在的周期类型（异步）.

    Args:
        session: AsyncSession 对象
        symbol: 证券代码
        interval_model_map: 周期到表模型的映射

    Returns:
        存在的周期类型列表
    """
    if interval_model_map is None:
        interval_model_map = INTERVAL_MODEL_MAP

    available_intervals = []

    for interval_name, model in interval_model_map.items():
        query = select(func.count()).where(model.symbol == symbol)
        result = await session.execute(query)
        count = result.scalar()

        if count > 0:
            available_intervals.append(interval_name)

    return available_intervals


async def get_data_range_for_symbol(
    session: AsyncSession,
    symbol: str,
    interval: str,
    interval_model_map: dict = None,
) -> tuple[Optional[datetime], Optional[datetime]]:
    """获取指定证券代码和周期的数据时间范围（异步）.

    Args:
        session: AsyncSession 对象
        symbol: 证券代码
        interval: K 线周期
        interval_model_map: 周期到表模型的映射

    Returns:
        (最早日期，最晚日期) 元组
    """
    if interval_model_map is None:
        interval_model_map = INTERVAL_MODEL_MAP

    interval_lower = interval.lower()
    if interval_lower not in interval_model_map:
        raise ValueError(f"不支持的周期: {interval}")

    table_model = interval_model_map[interval_lower]

    query = KlineDBInterface.build_range_query(table_model, symbol)
    result = await session.execute(query)
    row = result.first()

    return row[0], row[1]


# ==================== 异步保存函数 ====================

async def save_kline_to_db(
    session: AsyncSession,
    symbol: str,
    df: pd.DataFrame,
    interval: str,
    security_type: str = "stock",
    interval_model_map: dict = None,
) -> int:
    """异步保存单个证券的 K 线数据到数据库.

    Args:
        session: AsyncSession 对象
        symbol: 证券代码
        df: K 线数据 DataFrame
        interval: K 线周期
        security_type: 证券类型
        interval_model_map: 周期到表模型的映射

    Returns:
        保存的记录数
    """
    if df.empty:
        return 0

    if interval_model_map is None:
        interval_model_map = INTERVAL_MODEL_MAP

    interval_lower = interval.lower()
    if interval_lower not in interval_model_map:
        raise ValueError(f"不支持的周期: {interval}")

    # 包装为 kline_dict 格式调用批量保存
    kline_dict = {symbol: df}

    return await batch_save_kline_to_db(
        session=session,
        kline_dict=kline_dict,
        interval=interval,
        interval_model_map=interval_model_map,
    )


async def batch_save_kline_to_db(
    session: AsyncSession,
    kline_dict: Dict[str, pd.DataFrame],
    interval: str,
    interval_model_map: dict = None,
) -> int:
    """批量异步保存 K 线数据到数据库（使用 PostgreSQL UPSERT）.

    Args:
        session: AsyncSession 对象
        kline_dict: {symbol: DataFrame} 格式的 K 线数据
        interval: K 线周期
        interval_model_map: 周期到表模型的映射

    Returns:
        保存的记录总数
    """
    from galaxy_db_sync.shared_kernel.utils import infer_security_type

    if interval_model_map is None:
        interval_model_map = INTERVAL_MODEL_MAP

    interval_lower = interval.lower()
    if interval_lower not in interval_model_map:
        raise ValueError(f"不支持的周期: {interval}")

    table_model = interval_model_map[interval_lower]

    # 收集所有记录
    records = []

    for symbol, df in kline_dict.items():
        if df is None or df.empty:
            continue

        security_type = infer_security_type(symbol) or "stock"
        has_kline_time = "kline_time" in df.columns

        for idx, row in df.iterrows():
            try:
                # 解析交易时间
                if has_kline_time:
                    trade_time_value = parse_trade_time(row.get("kline_time"), idx)
                else:
                    trade_time_value = parse_trade_time(idx)

                # 提取行值
                values = extract_row_values(row)

                # 创建记录字典
                record = {
                    "symbol": symbol,
                    "trade_time": trade_time_value,
                    "open": values["open"],
                    "high": values["high"],
                    "low": values["low"],
                    "close": values["close"],
                    "volume": values["volume"],
                    "amount": values["amount"],
                    "security_type": security_type,
                }
                records.append(record)

            except Exception as e:
                logger.warning(f"创建记录失败 {symbol}: {e}")
                continue

    if not records:
        return 0

    return await _upsert_records(session, records, table_model)


async def _upsert_records(
    session: AsyncSession,
    records: List[dict],
    table_model,
    batch_size: int = 100,  # 每批最多100条，避免超过 asyncpg 参数限制
) -> int:
    """使用 PostgreSQL UPSERT 异步保存记录（分批处理）.

    Args:
        session: AsyncSession 对象
        records: 要保存的记录字典列表
        table_model: 数据库表模型
        batch_size: 每批处理的记录数（默认100，避免超过 asyncpg 32767 参数限制）

    Returns:
        保存的记录数
    """
    if not records:
        return 0

    try:
        # 按 (symbol, trade_time) 去重，保留最后一个
        seen = {}
        for record in records:
            key = (record["symbol"], record["trade_time"])
            seen[key] = record

        data_list = list(seen.values())

        if not data_list:
            return 0

        total_saved = 0

        # 分批保存，避免超过 asyncpg 参数限制
        for i in range(0, len(data_list), batch_size):
            batch = data_list[i : i + batch_size]

            # 使用 PostgreSQL UPSERT
            stmt = pg_insert(table_model).values(batch)
            update_dict = {
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "amount": stmt.excluded.amount,
                "security_type": stmt.excluded.security_type,
                "updated_at": func.now(),
            }
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "trade_time"],
                set_=update_dict,
            )

            await session.execute(upsert_stmt)
            total_saved += len(batch)

        await session.commit()
        # 使用 DEBUG 级别避免批量同步时大量日志输出
        logger.debug(f"批量异步保存 {len(data_list)} 条记录到数据库 (PostgreSQL UPSERT)")
        return len(data_list)

    except Exception as e:
        logger.error(f"PostgreSQL UPSERT 失败: {e}")
        await session.rollback()
        raise


# ==================== KlineService 类 ====================

class KlineService:
    """K 线异步数据服务类.

    使用依赖注入模式，通过构造函数接收 AsyncDatabaseManager 实例。
    不依赖全局 db_manager 单例，提高可测试性和灵活性。
    """

    def __init__(self, db_manager: AsyncDatabaseManager):
        """初始化 K 线服务.

        Args:
            db_manager: AsyncDatabaseManager 实例（通过依赖注入）
        """
        self._db_manager = db_manager
        self.interval_model_map = INTERVAL_MODEL_MAP

    def get_kline_table_by_interval(self, interval: str):
        """根据周期获取对应的表模型."""
        interval_lower = interval.lower()
        if interval_lower not in self.interval_model_map:
            raise ValueError(f"不支持的周期: {interval}")

        return self.interval_model_map[interval_lower]

    async def query_kline_from_db(
        self,
        symbols: List[str],
        start_date: Optional[Union[str, int, datetime]] = None,
        end_date: Optional[Union[str, int, datetime]] = None,
        interval: str = "day",
    ) -> Dict[str, pd.DataFrame]:
        """异步从数据库查询 K 线数据.

        Args:
            symbols: 证券代码列表
            start_date: 开始日期
            end_date: 结束日期
            interval: K 线周期

        Returns:
            以证券代码为键的 K 线数据 DataFrame 字典
        """
        async with self._db_manager.session() as session:
            return await query_kline_from_db(
                session=session,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                interval_model_map=self.interval_model_map,
            )

    async def save_kline_to_db(
        self,
        symbol: str,
        df: pd.DataFrame,
        interval: str,
        security_type: str = "stock",
    ) -> int:
        """异步将 K 线数据保存到数据库.

        Args:
            symbol: 证券代码
            df: K 线数据 DataFrame
            interval: K 线周期
            security_type: 证券类型

        Returns:
            保存的记录数
        """
        async with self._db_manager.session() as session:
            return await save_kline_to_db(
                session=session,
                symbol=symbol,
                df=df,
                interval=interval,
                security_type=security_type,
                interval_model_map=self.interval_model_map,
            )

    async def get_available_intervals_for_symbol(self, symbol: str) -> List[str]:
        """异步获取指定证券代码在数据库中存在的周期类型.

        Args:
            symbol: 证券代码

        Returns:
            存在的周期类型列表
        """
        async with self._db_manager.session() as session:
            return await get_available_intervals_for_symbol(
                session=session,
                symbol=symbol,
                interval_model_map=self.interval_model_map,
            )

    async def get_data_range_for_symbol(
        self,
        symbol: str,
        interval: str,
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """异步获取指定证券代码和周期的数据时间范围.

        Args:
            symbol: 证券代码
            interval: K 线周期

        Returns:
            (最早日期，最晚日期) 元组
        """
        async with self._db_manager.session() as session:
            return await get_data_range_for_symbol(
                session=session,
                symbol=symbol,
                interval=interval,
                interval_model_map=self.interval_model_map,
            )

    def merge_db_and_api_data(
        self,
        db_data: Dict[str, pd.DataFrame],
        api_data: Dict[str, pd.DataFrame],
    ) -> Dict[str, pd.DataFrame]:
        """合并数据库和 API 查询到的数据.

        注意：此方法为纯函数，不涉及数据库操作，不需要异步。

        Args:
            db_data: 从数据库查询到的数据
            api_data: 从 API 查询到的数据

        Returns:
            合并后的数据
        """
        merged_data = {}

        all_symbols = set(db_data.keys()).union(set(api_data.keys()))

        for symbol in all_symbols:
            db_df = db_data.get(symbol, pd.DataFrame())
            api_df = api_data.get(symbol, pd.DataFrame())

            if db_df.empty and api_df.empty:
                merged_data[symbol] = pd.DataFrame(
                    columns=[
                        "trade_time",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                        "amount",
                    ]
                )
            elif db_df.empty:
                merged_data[symbol] = api_df
            elif api_df.empty:
                merged_data[symbol] = db_df
            else:
                combined_df = pd.concat([db_df, api_df])
                combined_df = combined_df[~combined_df.index.duplicated(keep="last")]
                combined_df.sort_index(inplace=True)
                merged_data[symbol] = combined_df

        return merged_data

    async def batch_save_kline_to_db(
        self,
        kline_dict: Dict[str, pd.DataFrame],
        interval: str,
    ) -> int:
        """异步批量保存 K 线数据到数据库.

        Args:
            kline_dict: {symbol: DataFrame} 格式的 K 线数据
            interval: K 线周期

        Returns:
            保存的记录总数
        """
        async with self._db_manager.session() as session:
            return await batch_save_kline_to_db(
                session=session,
                kline_dict=kline_dict,
                interval=interval,
                interval_model_map=self.interval_model_map,
            )

    async def get_missing_date_ranges(
        self,
        symbol: str,
        interval: str,
        start_date: Union[str, int, datetime],
        end_date: Union[str, int, datetime],
    ) -> List[tuple[datetime, datetime]]:
        """兼容包装：返回 checker 计算出的缺失区间."""
        from galaxy_db_sync.database.services.kline_completeness_checker import (
            kline_completeness_checker,
        )

        completeness_result = await kline_completeness_checker.check_async(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
        )
        return [
            (
                datetime.combine(range_start, datetime.min.time()),
                datetime.combine(range_end, datetime.min.time()),
            )
            for range_start, range_end in completeness_result.missing_ranges
        ]

    async def check_data_completeness(
        self,
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
    ) -> tuple[bool, list[datetime]]:
        """兼容包装：返回是否完整以及 checker 展开的缺失日期列表."""
        from galaxy_db_sync.database.services.kline_completeness_checker import (
            kline_completeness_checker,
        )

        completeness_result = await kline_completeness_checker.check_async(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
        )
        missing_dates = [
            datetime.combine(missing_date, datetime.min.time())
            for missing_date in await kline_completeness_checker.get_missing_dates_async(
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
            )
        ]
        return completeness_result.is_complete, missing_dates


# 全局 K 线服务实例
from galaxy_db_sync.database.core.async_connection import async_db_manager
kline_service = KlineService(async_db_manager)