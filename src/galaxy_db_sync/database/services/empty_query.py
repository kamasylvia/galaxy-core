import logging
from datetime import date
from typing import List, Optional

from collections import defaultdict

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert

from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.core.async_connection import async_db_manager
from galaxy_db_sync.database.models.empty_query_result import EmptyQueryResult

logger = logging.getLogger(__name__)


class EmptyQueryResultService:
    """空查询结果缓存服务."""

    def is_confirmed_empty(
        self, symbol: str, interval: str, start_date: date, end_date: date
    ) -> bool:
        """检查指定区间是否已被确认为空数据."""
        try:
            with db_manager.session() as session:
                result = session.query(EmptyQueryResult).filter(
                    and_(
                        EmptyQueryResult.symbol == symbol,
                        EmptyQueryResult.interval == interval,
                        EmptyQueryResult.start_date <= start_date,
                        EmptyQueryResult.end_date >= end_date,
                    )
                ).first()
                return result is not None
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过空查询缓存检查")
                return False
            raise

    def record_empty_result(
        self, symbol: str, interval: str, start_date: date, end_date: date
    ) -> None:
        """记录一个空查询结果."""
        try:
            with db_manager.session() as session:
                existing = session.query(EmptyQueryResult).filter(
                    and_(
                        EmptyQueryResult.symbol == symbol,
                        EmptyQueryResult.interval == interval,
                        EmptyQueryResult.start_date <= start_date,
                        EmptyQueryResult.end_date >= end_date,
                    )
                ).first()

                if not existing:
                    record = EmptyQueryResult(
                        symbol=symbol,
                        interval=interval,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    session.merge(record)
                    session.commit()
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过空查询缓存写入")
                return
            raise

    # ==================== 异步方法 ====================

    async def is_confirmed_empty_async(
        self, symbol: str, interval: str, start_date: date, end_date: date
    ) -> bool:
        """检查指定区间是否已被确认为空数据（异步版本）."""
        try:
            async with async_db_manager.session() as session:
                stmt = select(EmptyQueryResult).where(
                    and_(
                        EmptyQueryResult.symbol == symbol,
                        EmptyQueryResult.interval == interval,
                        EmptyQueryResult.start_date <= start_date,
                        EmptyQueryResult.end_date >= end_date,
                    )
                )
                result = await session.execute(stmt)
                return result.scalars().first() is not None
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过空查询缓存检查")
                return False
            raise

    async def record_empty_result_async(
        self, symbol: str, interval: str, start_date: date, end_date: date
    ) -> None:
        """记录一个空查询结果（异步版本）."""
        try:
            async with async_db_manager.session() as session:
                stmt = select(EmptyQueryResult).where(
                    and_(
                        EmptyQueryResult.symbol == symbol,
                        EmptyQueryResult.interval == interval,
                        EmptyQueryResult.start_date <= start_date,
                        EmptyQueryResult.end_date >= end_date,
                    )
                )
                result = await session.execute(stmt)
                existing = result.scalars().first()

                if not existing:
                    record = EmptyQueryResult(
                        symbol=symbol,
                        interval=interval,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    await session.merge(record)
                    await session.commit()
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过空查询缓存写入")
                return
            raise

    # ==================== 批量方法 ====================

    def batch_is_confirmed_empty(
        self,
        interval: str,
        symbols_and_ranges: list[tuple[str, date, date]],
    ) -> set[str]:
        """批量检查空查询结果（同步版本）.

        Args:
            interval: K线周期
            symbols_and_ranges: [(symbol, start_date, end_date), ...]

        Returns:
            已被确认空的 (symbol|start|end) 标识符集合
        """
        if not symbols_and_ranges:
            return set()

        symbols = list({s for s, _, _ in symbols_and_ranges})

        try:
            with db_manager.session() as session:
                records = (
                    session.query(EmptyQueryResult)
                    .filter(
                        and_(
                            EmptyQueryResult.interval == interval,
                            EmptyQueryResult.symbol.in_(symbols),
                        )
                    )
                    .all()
                )
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过空查询缓存检查")
                return set()
            raise

        empty_by_symbol: dict[str, list[tuple[date, date]]] = defaultdict(list)
        for r in records:
            empty_by_symbol[r.symbol].append((r.start_date, r.end_date))

        confirmed: set[str] = set()
        for symbol, range_start, range_end in symbols_and_ranges:
            for empty_start, empty_end in empty_by_symbol.get(symbol, []):
                if empty_start <= range_start and empty_end >= range_end:
                    confirmed.add(
                        f"{symbol}|{range_start.isoformat()}|{range_end.isoformat()}"
                    )
                    break

        return confirmed

    async def batch_is_confirmed_empty_async(
        self,
        interval: str,
        symbols_and_ranges: list[tuple[str, date, date]],
    ) -> set[str]:
        """批量检查空查询结果（异步版本）.

        Args:
            interval: K线周期
            symbols_and_ranges: [(symbol, start_date, end_date), ...]

        Returns:
            已被确认空的 (symbol|start|end) 标识符集合
        """
        if not symbols_and_ranges:
            return set()

        symbols = list({s for s, _, _ in symbols_and_ranges})

        try:
            async with async_db_manager.session() as session:
                stmt = select(EmptyQueryResult).where(
                    and_(
                        EmptyQueryResult.interval == interval,
                        EmptyQueryResult.symbol.in_(symbols),
                    )
                )
                result = await session.execute(stmt)
                records = result.scalars().all()
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过空查询缓存检查")
                return set()
            raise

        empty_by_symbol: dict[str, list[tuple[date, date]]] = defaultdict(list)
        for r in records:
            empty_by_symbol[r.symbol].append((r.start_date, r.end_date))

        confirmed: set[str] = set()
        for symbol, range_start, range_end in symbols_and_ranges:
            for empty_start, empty_end in empty_by_symbol.get(symbol, []):
                if empty_start <= range_start and empty_end >= range_end:
                    confirmed.add(
                        f"{symbol}|{range_start.isoformat()}|{range_end.isoformat()}"
                    )
                    break

        return confirmed

    def batch_record_empty_results(
        self,
        interval: str,
        records: list[tuple[str, date, date]],
    ) -> None:
        """批量记录空查询结果（同步版本）.

        使用 INSERT ... ON CONFLICT DO NOTHING 跳过已存在记录。
        """
        if not records:
            return

        values = [
            {
                "symbol": symbol,
                "interval": interval,
                "start_date": range_start,
                "end_date": range_end,
            }
            for symbol, range_start, range_end in records
        ]

        try:
            with db_manager.session() as session:
                stmt = (
                    insert(EmptyQueryResult)
                    .values(values)
                    .on_conflict_do_nothing(
                        index_elements=["symbol", "interval", "start_date", "end_date"]
                    )
                )
                session.execute(stmt)
                session.commit()
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过空查询缓存批量写入")
                return
            raise

    async def batch_record_empty_results_async(
        self,
        interval: str,
        records: list[tuple[str, date, date]],
    ) -> None:
        """批量记录空查询结果（异步版本）.

        使用 INSERT ... ON CONFLICT DO NOTHING 跳过已存在记录。
        """
        if not records:
            return

        values = [
            {
                "symbol": symbol,
                "interval": interval,
                "start_date": range_start,
                "end_date": range_end,
            }
            for symbol, range_start, range_end in records
        ]

        try:
            async with async_db_manager.session() as session:
                stmt = (
                    insert(EmptyQueryResult)
                    .values(values)
                    .on_conflict_do_nothing(
                        index_elements=["symbol", "interval", "start_date", "end_date"]
                    )
                )
                await session.execute(stmt)
                await session.commit()
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过空查询缓存批量写入")
                return
            raise


empty_query_service = EmptyQueryResultService()
