"""K 线数据服务层 (异步版本).

提供 K 线数据的异步数据库操作接口，包括查询、保存等功能。
使用依赖注入模式，不依赖全局 db_manager 单例。
"""

import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.database.models.kline import INTERVAL_MODEL_MAP, BaseKlineMinute
from galaxy_core.shared_kernel.nocodb_schema import expand_security_type
from galaxy_core.shared_kernel.utils.constants import CST
from galaxy_core.shared_kernel.utils.time_parser import expand_date_to_full

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


def parse_trade_time(value, idx=None) -> datetime:
    """解析交易时间值.

    返回带北京时区(CST)的 aware datetime。SDK 返回的时间字面值是北京 wall-clock,
    入库前 attach CST tzinfo,否则 timestamptz 列会把 naive 当 UTC 写入,偏移 8 小时。

    Args:
        value: 时间值（可能是多种类型）
        idx: 备用索引值

    Returns:
        aware datetime 对象(北京时区)
    """
    from galaxy_core.shared_kernel.utils.constants import localize_cst

    if isinstance(value, datetime):
        return localize_cst(value)

    if value is None or (isinstance(value, float) and pd.isna(value)):
        # 使用备用索引
        if idx is not None:
            return parse_trade_time(idx)
        raise ValueError("无法解析交易时间")

    if isinstance(value, str):
        try:
            return localize_cst(datetime.strptime(value[:8], "%Y%m%d"))
        except ValueError:
            try:
                return localize_cst(datetime.strptime(value, '%Y-%m-%d'))
            except ValueError:
                pass
    elif isinstance(value, int):
        try:
            return localize_cst(datetime.strptime(str(value)[:8], "%Y%m%d"))
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


def parse_trade_time_vectorized(
    series: pd.Series, fallback_series: pd.Series | None = None
) -> tuple[pd.Series, list]:
    """向量化解析交易时间.

    使用 pd.to_datetime 替代逐行 parse_trade_time，性能显著提升。

    Args:
        series: 时间值 Series（可能是 datetime/str/int/NaN 混合类型）
        fallback_series: 备用索引 Series（当主值解析失败时使用）

    Returns:
        (parsed_datetime_series, error_row_indices_list)
    """
    # Step 1: 处理已经是 datetime 的情况
    if pd.api.types.is_datetime64_any_dtype(series):
        localized = _localize_series_cst(series.copy())
        return localized, []

    # 统一 fallback 为 Series（caller 可能传 pd.Index，如 df.index）
    if fallback_series is not None and not isinstance(fallback_series, pd.Series):
        fallback_series = pd.Series(fallback_series, index=series.index)

    # Step 2: 转为 object dtype 后统一处理（避免 int64 dtype 赋值字符串报错）
    is_null = series.isna()
    str_series = series.astype(object)

    # 非空值转为字符串
    non_null_mask = ~is_null
    if non_null_mask.any():
        str_series[non_null_mask] = str_series[non_null_mask].astype(str).str.strip()

    # Step 3: 尝试 %Y%m%d 格式（8位数字字符串）
    # 统一为 datetime64[ns] 避免后续 fallback 赋值时 [s]/[ns] dtype 冲突
    result = pd.to_datetime(str_series, format="%Y%m%d", errors="coerce").astype("datetime64[ns]")

    # Step 4: 对仍为 NaT 的行，尝试自动推断
    still_nat = result.isna() & non_null_mask
    if still_nat.any():
        result[still_nat] = pd.to_datetime(str_series[still_nat], errors="coerce")

    # Step 5: 对仍为 NaT 的行，使用 fallback
    final_nat = result.isna()
    error_indices = []

    if fallback_series is not None and final_nat.any():
        fallback_mask = final_nat & fallback_series.notna()
        if fallback_mask.any():
            fallback_subset = fallback_series[fallback_mask]
            # 防御：fallback 为整数型（如 RangeIndex 行号 0,1,2）时，
            # pd.to_datetime 会误把整数当 nanoseconds → 1970-01-01 假成功。
            # 仅当 fallback 看起来是日期语义（字符串/datetime/大整数 YYYYMMDD）才使用。
            fallback_usable = True
            if pd.api.types.is_integer_dtype(fallback_subset):
                max_val = fallback_subset.max()
                # YYYYMMDD 格式整数最小合理值（19900101），小于此视为行号等无意义整数
                if max_val < 19900101:
                    fallback_usable = False

            if fallback_usable:
                fallback_parsed = pd.to_datetime(fallback_subset, errors="coerce")
                result.loc[fallback_mask] = fallback_parsed.to_numpy()
            # fallback 不可用时 result 保持 NaT，由下方 final_nat 统一收集错误
        # 更新最终 NaT
        final_nat = result.isna()

    # 收集所有最终失败的行索引
    if final_nat.any():
        new_errors = list(result[final_nat].index)
        error_indices.extend(new_errors)
        if new_errors:
            logger.warning(f"无法解析 {len(new_errors)} 行交易时间，索引: {new_errors[:10]}...")

    # localize naive result 到北京时区(SDK 字面值是北京 wall-clock)
    result = _localize_series_cst(result)
    return result, error_indices


def _localize_series_cst(series: pd.Series) -> pd.Series:
    """把 datetime64 Series localize 到北京时区.

    naive → attach CST;aware → convert CST。
    NaT 值保持 NaT(pandas tz_localize 对 NaT 透明)。
    兼容输入是 pd.Series(.dt accessor)或 pd.DatetimeIndex(.tz 直接属性)。
    """
    from galaxy_core.shared_kernel.utils.constants import CST

    # 统一处理:Series 用 .dt,DatetimeIndex 直接 .tz
    if isinstance(series, pd.Series):
        tz = series.dt.tz
        if tz is None:
            return series.dt.tz_localize(CST)
        return series.dt.tz_convert(CST)
    else:
        # DatetimeIndex 或类似
        tz = getattr(series, "tz", None)
        if tz is None:
            return series.tz_localize(CST)
        return series.tz_convert(CST)


def extract_records_vectorized(df: pd.DataFrame) -> list[dict]:
    """向量化提取 OHLCV 记录.

    使用 pd.to_numeric + to_dict('records') 替代逐行 extract_row_values。

    Args:
        df: 包含 open/high/low/close/volume/amount 列的 DataFrame

    Returns:
        记录字典列表
    """
    OHLCV_COLS = ["open", "high", "low", "close", "volume", "amount"]

    # 只取需要的列
    df_out = df[OHLCV_COLS].copy()

    # 数值类型转换
    for col in ["open", "high", "low", "close", "amount"]:
        if col in df_out.columns:
            df_out[col] = pd.to_numeric(df_out[col], errors="coerce")

    # volume 转为 nullable int
    if "volume" in df_out.columns:
        df_out["volume"] = pd.to_numeric(df_out["volume"], errors="coerce").astype("Int64")

    # NaN → None，转为 object dtype 后替换
    df_obj = df_out.astype(object)
    df_obj = df_obj.where(df_out.notna(), None)
    records = df_obj.to_dict("records")
    return records


# ==================== 异步查询函数 ====================

async def query_kline_from_db(
    session: AsyncSession,
    symbols: list[str],
    start_date: str | int | datetime | None = None,
    end_date: str | int | datetime | None = None,
    interval: str = "day",
    interval_model_map: dict = None,
) -> dict[str, pd.DataFrame]:
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

    start_dt = datetime.strptime(expand_date_to_full(str(start_date), interval, is_end=False), "%Y%m%d") if start_date else None
    end_dt = datetime.strptime(expand_date_to_full(str(end_date), interval, is_end=True), "%Y%m%d") if end_date else None

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
) -> list[str]:
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
) -> tuple[datetime | None, datetime | None]:
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
    kline_dict: dict[str, pd.DataFrame],
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
    from galaxy_core.shared_kernel.utils import infer_security_type

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

        # 向量化解析交易时间
        if has_kline_time:
            time_col = df["kline_time"]
            fallback = df.index
        else:
            time_col = df.index
            fallback = None

        parsed_times, error_indices = parse_trade_time_vectorized(time_col, fallback_series=fallback)

        if error_indices:
            logger.warning(f"{symbol}: {len(error_indices)} 行交易时间解析失败，已跳过")

        # 向量化提取 OHLCV 记录
        ohlcv_records = extract_records_vectorized(df)

        # 长 K trade_time=Date(北京日期);分钟 K trade_time=naive 北京 wall-clock
        is_minute = issubclass(table_model, BaseKlineMinute)

        # 合并 symbol, trade_time, security_type(nocodb 多值形态)
        for rec, trade_time in zip(ohlcv_records, parsed_times):
            if pd.isna(trade_time):
                continue
            rec["symbol"] = symbol
            if is_minute:
                rec["trade_time"] = trade_time.tz_convert(CST).tz_localize(None).to_pydatetime()
            else:
                rec["trade_time"] = trade_time.tz_convert(CST).date()
            rec["security_type"] = expand_security_type(security_type)
            records.append(rec)

    if not records:
        return 0

    return await _upsert_records(session, records, table_model)


async def _upsert_records(
    session: AsyncSession,
    records: list[dict],
    table_model,
    batch_size: int | None = None,
) -> int:
    """使用 PostgreSQL UPSERT 异步保存记录（分批处理）.

    Args:
        session: AsyncSession 对象
        records: 要保存的记录字典列表
        table_model: 数据库表模型
        batch_size: 每批处理的记录数（默认从配置加载，避免超过 asyncpg 32767 参数限制）

    Returns:
        保存的记录数
    """
    from galaxy_core.shared_kernel.utils.config_loader import get_config

    if batch_size is None:
        batch_size = get_config("sync.batch", "db_upsert", 100)
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
        symbols: list[str],
        start_date: str | int | datetime | None = None,
        end_date: str | int | datetime | None = None,
        interval: str = "day",
    ) -> dict[str, pd.DataFrame]:
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

    async def get_available_intervals_for_symbol(self, symbol: str) -> list[str]:
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
    ) -> tuple[datetime | None, datetime | None]:
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
        db_data: dict[str, pd.DataFrame],
        api_data: dict[str, pd.DataFrame],
    ) -> dict[str, pd.DataFrame]:
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
        kline_dict: dict[str, pd.DataFrame],
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

