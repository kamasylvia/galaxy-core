import logging
from datetime import date
from typing import List, Optional

from sqlalchemy import and_, select

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
                return result.scalar_one_or_none() is not None
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
                existing = result.scalar_one_or_none()

                if not existing:
                    record = EmptyQueryResult(
                        symbol=symbol,
                        interval=interval,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    session.add(record)
                    await session.commit()
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过空查询缓存写入")
                return
            raise


empty_query_service = EmptyQueryResultService()
