"""K线数据存储适配器 — 直接操作 SQLAlchemy model 为 KlineStorePort."""

import contextlib
import logging
from datetime import date, datetime

from sqlalchemy import String, and_, bindparam, func, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.database.models.kline import INTERVAL_MODEL_MAP, BaseKlineMinute
from galaxy_core.domain.date_range.parser import expand_date_to_full
from galaxy_core.domain.value_objects import Interval, KlineBar, SecurityType
from galaxy_core.shared_kernel.exceptions import CacheError
from galaxy_core.shared_kernel.nocodb_schema import expand_security_type
from galaxy_core.shared_kernel.utils.constants import CST

logger = logging.getLogger(__name__)


class KlineStoreAdapter:
    """KlineStorePort 实现 — 直接操作 SQLAlchemy model.

    不通过现有 KlineService 类中转，直接操作数据库。
    """

    def __init__(self, db_manager: AsyncDatabaseManager) -> None:
        self._db = db_manager

    async def save_kline(
        self,
        data: list[KlineBar],
        interval: Interval,
    ) -> None:
        """保存K线数据到数据库.

        使用 PostgreSQL UPSERT 模式，按 (symbol, trade_time) 去重。

        Args:
            data: KlineBar 列表
            interval: K线周期
        """
        if not data:
            return

        table_model = INTERVAL_MODEL_MAP[interval.value]

        # nocodb 形态:长 K trade_time=date(北京日期);分钟 K=naive 北京 wall-clock;
        # security_type=多值串(市场码+大类码,见 nocodb_schema.SECURITY_TYPE_EXPAND)
        is_minute = issubclass(table_model, BaseKlineMinute)

        def _fit_trade_time(v: datetime) -> date | datetime:
            if isinstance(v, datetime):
                v = v.astimezone(CST) if v.tzinfo else v
                return v.replace(tzinfo=None) if is_minute else v.date()
            return v  # 已是 date

        # KlineBar → list[dict] 转换
        records = [
            {
                "symbol": bar.symbol,
                "trade_time": _fit_trade_time(bar.trade_time),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "amount": bar.amount,
                "security_type": (
                    expand_security_type(bar.security_type.value) if bar.security_type else None
                ),
                **({"is_final": bar.is_final} if is_minute else {}),
            }
            for bar in data
        ]

        try:
            async with self._db.session() as session:
                # 按 (symbol, trade_time) 去重，保留最后一个
                seen: dict[tuple[str, datetime], dict] = {}
                for rec in records:
                    key = (rec["symbol"], rec["trade_time"])
                    seen[key] = rec
                data_list = list(seen.values())

                if not data_list:
                    return

                # 分批处理，避免 asyncpg 参数限制
                from galaxy_core.shared_kernel.utils.config_loader import get_config

                batch_size = get_config("sync.batch", "db_upsert", 100)
                if not isinstance(batch_size, int):
                    batch_size = 100

                for i in range(0, len(data_list), batch_size):
                    batch = data_list[i : i + batch_size]

                    # PostgreSQL UPSERT
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
                    if is_minute:
                        update_dict["is_final"] = stmt.excluded.is_final
                    upsert_stmt = stmt.on_conflict_do_update(
                        index_elements=["symbol", "trade_time"],
                        set_=update_dict,
                    )
                    await session.execute(upsert_stmt)
        except SQLAlchemyError as e:
            raise CacheError(
                message=f"保存K线数据失败: {e}",
                operation="save_kline",
                key=f"{interval.value}:{len(data)}条",
            ) from e

        logger.debug(f"保存 {len(data_list)} 条K线数据，interval={interval.value}")

    async def get_kline(
        self,
        symbol: str,
        interval: Interval,
        start: str,
        end: str,
    ) -> list[KlineBar]:
        """从数据库查询K线数据.

        Args:
            symbol: 证券代码
            interval: K线周期
            start: 开始日期 (YYYYMMDD 格式字符串)
            end: 结束日期 (YYYYMMDD 格式字符串)

        Returns:
            KlineBar 列表
        """
        table_model = INTERVAL_MODEL_MAP[interval.value]

        # 解析日期边界 → 北京时区 aware datetime(timestamptz 列比较需要)
        from galaxy_core.shared_kernel.utils.constants import localize_cst

        start_dt = localize_cst(_parse_date_str(start, interval.value, is_end=False))
        end_dt = localize_cst(_parse_date_str(end, interval.value, is_end=True))

        try:
            async with self._db.session() as session:
                stmt = (
                    select(table_model)
                    .where(
                        and_(
                            table_model.symbol == symbol,
                            table_model.trade_time >= start_dt,
                            table_model.trade_time <= end_dt,
                        )
                    )
                    .order_by(table_model.trade_time)
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()
        except SQLAlchemyError as e:
            raise CacheError(
                message=f"查询K线数据失败: {e}",
                operation="get_kline",
                key=f"{symbol}:{interval.value}",
            ) from e

        # DB records → KlineBar
        bars: list[KlineBar] = []
        for row in rows:
            security_type = None
            if row.security_type:
                with contextlib.suppress(ValueError):
                    security_type = SecurityType(row.security_type)

            bars.append(
                KlineBar(
                    symbol=row.symbol,
                    trade_time=row.trade_time,
                    open=row.open,
                    high=row.high,
                    low=row.low,
                    close=row.close,
                    volume=row.volume,
                    amount=row.amount,
                    security_type=security_type or SecurityType.EXTRA_STOCK_A,
                )
            )

        logger.debug(f"查询到 {len(bars)} 条K线，symbol={symbol}, interval={interval.value}")
        return bars

    async def get_last_sync_dates(
        self,
        symbols: list[str],
        interval: Interval,
    ) -> dict[str, date | None]:
        """批量查询 symbol 的最后同步日期.

        缺失记录自动从K线表 MAX(trade_time) 回填，避免全量重同步。

        Args:
            symbols: 证券代码列表
            interval: K线周期

        Returns:
            dict[symbol, last_sync_date]，未查到记录的 symbol 不包含在返回中
        """
        if not symbols:
            return {}

        from galaxy_core.database.models.last_sync_date import LastSyncDate

        found: dict[str, date] = {}
        try:
            async with self._db.session() as session:
                # 使用 PostgreSQL = ANY(:symbols) 数组语法避免 IN 子句参数过多
                stmt = select(LastSyncDate).where(
                    and_(
                        LastSyncDate.symbol
                        == func.any(bindparam("symbols", value=symbols, type_=ARRAY(String))),
                        LastSyncDate.interval == interval.value,
                    )
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()
                for row in rows:
                    found[row.symbol] = row.last_sync_date
        except SQLAlchemyError as e:
            raise CacheError(
                message=f"查询最后同步日期失败: {e}",
                operation="get_last_sync_dates",
                key=f"{len(symbols)} symbols:{interval.value}",
            ) from e

        # 回填缺失记录：从K线表查 MAX(trade_time)
        missing = [s for s in symbols if s not in found]
        if missing:
            backfilled = await self._backfill_from_kline(missing, interval)
            if backfilled:
                await self.set_last_sync_dates(backfilled, interval)
                found.update(backfilled)
                logger.info(
                    f"从K线表回填 {len(backfilled)} 个 symbol 的 last_sync_date "
                    f"(interval={interval.value})"
                )

        return found

    async def _backfill_from_kline(self, symbols: list[str], interval: Interval) -> dict[str, date]:
        """从K线表查 MAX(trade_time) 回填 last_sync_date."""
        table_model = INTERVAL_MODEL_MAP.get(interval.value)
        if table_model is None:
            return {}

        result: dict[str, date] = {}
        # 分钟表只认 is_final=true 行(2026-10-28):realtime_sub 盘中写的是
        # is_final=false 的稀疏 bar(14:00 起订,日均 ~60 根/只),MAX(trade_time)
        # 把 last_sync_date 顶到当日后,定稿覆盖的「需同步」判定会永久跳过该日,
        # 09:30-14:00 段无 API 回补(10/27 实证:1627/1630 只 <100 bar 却标
        # success)。分钟周期回填只统计已定稿行;day/week 表无 is_final 列不受影响。
        minute_intervals = ("min1", "min3", "min5", "min10", "min15", "min30", "min60", "min120")
        try:
            async with self._db.session() as session:
                # DISTINCT ON 替代 GROUP BY + MAX，避免哈希聚合内存溢出。
                # (symbol, trade_time) 复合索引使 PostgreSQL 只需扫描每 symbol
                # 最后一条记录，无需 GROUP BY 的哈希表或排序缓冲。
                conditions = [
                    table_model.symbol
                    == func.any(bindparam("symbols", value=symbols, type_=ARRAY(String)))
                ]
                if interval.value in minute_intervals:
                    conditions.append(table_model.is_final.is_(True))
                stmt = (
                    select(
                        table_model.symbol,
                        table_model.trade_time.label("max_date"),
                    )
                    .distinct(table_model.symbol)
                    .where(*conditions)
                    .order_by(table_model.symbol, table_model.trade_time.desc())
                )
                rows = await session.execute(stmt)
                for row in rows:
                    max_dt = row.max_date
                    if isinstance(max_dt, datetime):
                        # aware datetime → 北京时区后取 date(timestamptz 读出后转 CST)
                        from galaxy_core.shared_kernel.utils.constants import CST

                        max_dt = max_dt.astimezone(CST).date()
                    if isinstance(max_dt, date):
                        result[row.symbol] = max_dt
        except SQLAlchemyError as e:
            logger.warning(f"回填 last_sync_date 失败: {e}")

        return result

    async def set_last_sync_dates(
        self,
        symbol_dates: dict[str, date],
        interval: Interval,
    ) -> None:
        """批量 upsert 最后同步日期.

        使用 PostgreSQL UPSERT（INSERT ... ON CONFLICT DO UPDATE）确保幂等。

        Args:
            symbol_dates: {symbol: last_sync_date} 映射
            interval: K线周期
        """
        if not symbol_dates:
            return

        from galaxy_core.database.models.last_sync_date import LastSyncDate

        records = [
            {
                "symbol": s,
                "interval": interval.value,
                "last_sync_date": dt,
            }
            for s, dt in symbol_dates.items()
        ]

        try:
            async with self._db.session() as session:
                stmt = pg_insert(LastSyncDate).values(records)
                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol", "interval"],
                    set_={
                        "last_sync_date": stmt.excluded.last_sync_date,
                        "updated_at": func.now(),
                    },
                )
                await session.execute(upsert_stmt)
        except SQLAlchemyError as e:
            raise CacheError(
                message=f"更新最后同步日期失败: {e}",
                operation="set_last_sync_dates",
                key=f"{len(symbol_dates)} symbols:{interval.value}",
            ) from e

        logger.debug(
            f"更新 {len(symbol_dates)} 个 symbol 的 last_sync_date, interval={interval.value}"
        )


def _parse_date_str(date_str: str, interval: str = "day", is_end: bool = False) -> datetime:
    """解析日期字符串为 datetime.

    端口约定 start/end 为 8 位 YYYYMMDD 格式字符串。
    对于较短格式（4 位年份、6 位年月），根据周期做补全。

    Args:
        date_str: 日期字符串
        interval: 周期类型，用于确定补全规则
        is_end: 是否为结束日期
    """
    expanded = expand_date_to_full(date_str, interval=interval, is_end=is_end)
    return datetime.strptime(expanded[:8], "%Y%m%d")
