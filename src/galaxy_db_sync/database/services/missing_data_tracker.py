"""缺失数据追踪服务.

管理完整性检查结果的追踪和缺失数据确认。
"""

import logging
from datetime import date, datetime
from typing import List, Optional, Tuple

from sqlalchemy import and_, select, delete

from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.core.async_connection import async_db_manager
from galaxy_db_sync.database.models.completeness_check_result import (
    CompletenessCheckResult,
    MissingDataConfirmation,
)

logger = logging.getLogger(__name__)


class MissingDataTracker:
    """缺失数据追踪服务.

    功能：
    1. 记录完整性检查发现的缺失
    2. 查询已知的缺失（避免重复检查）
    3. 确认缺失原因（API返回空、停牌等）
    """

    def record_missing_range(
        self,
        symbol: str,
        interval: str,
        check_start: date,
        check_end: date,
        missing_start: date,
        missing_end: date,
    ) -> None:
        """记录完整性检查发现的缺失范围."""
        try:
            with db_manager.session() as session:
                # 检查是否已有记录
                existing = session.query(CompletenessCheckResult).filter(
                    and_(
                        CompletenessCheckResult.symbol == symbol,
                        CompletenessCheckResult.interval == interval,
                        CompletenessCheckResult.missing_start == missing_start,
                        CompletenessCheckResult.missing_end == missing_end,
                    )
                ).first()

                if existing:
                    # 更新最后检查时间
                    existing.last_checked_at = datetime.now()
                    session.commit()
                    logger.debug(
                        f"{symbol}: 更新已有缺失记录 {missing_start}~{missing_end}"
                    )
                else:
                    # 创建新记录
                    record = CompletenessCheckResult(
                        symbol=symbol,
                        interval=interval,
                        check_start=check_start,
                        check_end=check_end,
                        missing_start=missing_start,
                        missing_end=missing_end,
                        is_confirmed_missing=False,
                    )
                    session.add(record)
                    session.commit()
                    logger.debug(
                        f"{symbol}: 记录新缺失范围 {missing_start}~{missing_end}"
                    )
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过缺失记录")
                return
            raise

    def get_known_missing_ranges(
        self,
        symbol: str,
        interval: str,
        check_start: date,
        check_end: date,
    ) -> List[Tuple[date, date]]:
        """获取已知的缺失范围（未确认的）."""
        try:
            with db_manager.session() as session:
                results = session.query(CompletenessCheckResult).filter(
                    and_(
                        CompletenessCheckResult.symbol == symbol,
                        CompletenessCheckResult.interval == interval,
                        CompletenessCheckResult.check_start <= check_start,
                        CompletenessCheckResult.check_end >= check_end,
                        CompletenessCheckResult.is_confirmed_missing == False,
                    )
                ).all()

                return [(r.missing_start, r.missing_end) for r in results]
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，返回空列表")
                return []
            raise

    def get_confirmed_missing_ranges(
        self,
        symbol: str,
        interval: str,
    ) -> List[Tuple[date, date, str]]:
        """获取已确认的缺失范围（API返回空的）.

        返回: [(missing_start, missing_end, confirmation_reason), ...]
        """
        try:
            with db_manager.session() as session:
                results = session.query(CompletenessCheckResult).filter(
                    and_(
                        CompletenessCheckResult.symbol == symbol,
                        CompletenessCheckResult.interval == interval,
                        CompletenessCheckResult.is_confirmed_missing == True,
                    )
                ).all()

                return [
                    (r.missing_start, r.missing_end, r.confirmation_reason or "UNKNOWN")
                    for r in results
                ]
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                return []
            raise

    def confirm_missing_as_api_empty(
        self,
        symbol: str,
        interval: str,
        missing_start: date,
        missing_end: date,
        api_response: Optional[str] = None,
    ) -> None:
        """确认缺失是因为 API 返回空数据."""
        try:
            with db_manager.session() as session:
                # 更新 CompletenessCheckResult
                result = session.query(CompletenessCheckResult).filter(
                    and_(
                        CompletenessCheckResult.symbol == symbol,
                        CompletenessCheckResult.interval == interval,
                        CompletenessCheckResult.missing_start == missing_start,
                        CompletenessCheckResult.missing_end == missing_end,
                    )
                ).first()

                if result:
                    result.is_confirmed_missing = True
                    result.confirmation_reason = "API_EMPTY"
                    result.api_empty_checked_at = datetime.now()
                    session.commit()
                    logger.debug(
                        f"{symbol}: 确认缺失 {missing_start}~{missing_end} 为 API_EMPTY"
                    )
                else:
                    # 创建已确认的记录
                    record = CompletenessCheckResult(
                        symbol=symbol,
                        interval=interval,
                        check_start=missing_start,
                        check_end=missing_end,
                        missing_start=missing_start,
                        missing_end=missing_end,
                        is_confirmed_missing=True,
                        confirmation_reason="API_EMPTY",
                        api_empty_checked_at=datetime.now(),
                    )
                    session.add(record)
                    session.commit()
                    logger.debug(
                        f"{symbol}: 创建已确认缺失记录 {missing_start}~{missing_end} (API_EMPTY)"
                    )

                # 同时记录到 MissingDataConfirmation
                confirmation = MissingDataConfirmation(
                    symbol=symbol,
                    interval=interval,
                    missing_start=missing_start,
                    missing_end=missing_end,
                    confirmation_type="API_EMPTY",
                    api_response=api_response,
                )
                session.add(confirmation)
                session.commit()

        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过确认记录")
                return
            raise

    def clear_resolved_missing(
        self,
        symbol: str,
        interval: str,
        missing_start: date,
        missing_end: date,
    ) -> None:
        """清除已修复的缺失记录."""
        try:
            with db_manager.session() as session:
                session.execute(
                    delete(CompletenessCheckResult).where(
                        and_(
                            CompletenessCheckResult.symbol == symbol,
                            CompletenessCheckResult.interval == interval,
                            CompletenessCheckResult.missing_start == missing_start,
                            CompletenessCheckResult.missing_end == missing_end,
                        )
                    )
                )
                session.commit()
                logger.info(
                    f"{symbol}: 清除已修复的缺失记录 {missing_start}~{missing_end}"
                )
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                return
            raise

    def is_range_confirmed_missing(
        self,
        symbol: str,
        interval: str,
        start_date: date,
        end_date: date,
    ) -> bool:
        """检查指定范围是否已确认为缺失（API返回空）.

        检查逻辑：请求范围是否被已确认的缺失范围完全覆盖。
        即：存在一条已确认记录，其 missing_start <= start_date 且 missing_end >= end_date。
        """
        try:
            with db_manager.session() as session:
                result = session.query(CompletenessCheckResult).filter(
                    and_(
                        CompletenessCheckResult.symbol == symbol,
                        CompletenessCheckResult.interval == interval,
                        CompletenessCheckResult.missing_start <= start_date,
                        CompletenessCheckResult.missing_end >= end_date,
                        CompletenessCheckResult.is_confirmed_missing == True,
                    )
                ).first()
                return result is not None
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                return False
            raise

    # ==================== 异步方法 ====================

    async def record_missing_range_async(
        self,
        symbol: str,
        interval: str,
        check_start: date,
        check_end: date,
        missing_start: date,
        missing_end: date,
    ) -> None:
        """记录完整性检查发现的缺失范围（异步版本）."""
        try:
            async with async_db_manager.session() as session:
                # 检查是否已有记录
                stmt = select(CompletenessCheckResult).where(
                    and_(
                        CompletenessCheckResult.symbol == symbol,
                        CompletenessCheckResult.interval == interval,
                        CompletenessCheckResult.missing_start == missing_start,
                        CompletenessCheckResult.missing_end == missing_end,
                    )
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    existing.last_checked_at = datetime.now()
                    await session.commit()
                    logger.debug(f"{symbol}: 更新已有缺失记录 {missing_start}~{missing_end}")
                else:
                    record = CompletenessCheckResult(
                        symbol=symbol,
                        interval=interval,
                        check_start=check_start,
                        check_end=check_end,
                        missing_start=missing_start,
                        missing_end=missing_end,
                        is_confirmed_missing=False,
                    )
                    session.add(record)
                    await session.commit()
                    logger.debug(f"{symbol}: 记录新缺失范围 {missing_start}~{missing_end}")
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过缺失记录")
                return
            raise

    async def get_known_missing_ranges_async(
        self,
        symbol: str,
        interval: str,
        check_start: date,
        check_end: date,
    ) -> List[Tuple[date, date]]:
        """获取已知的缺失范围（未确认的）- 异步版本."""
        try:
            async with async_db_manager.session() as session:
                stmt = select(CompletenessCheckResult).where(
                    and_(
                        CompletenessCheckResult.symbol == symbol,
                        CompletenessCheckResult.interval == interval,
                        CompletenessCheckResult.check_start <= check_start,
                        CompletenessCheckResult.check_end >= check_end,
                        CompletenessCheckResult.is_confirmed_missing == False,
                    )
                )
                result = await session.execute(stmt)
                results = result.scalars().all()
                return [(r.missing_start, r.missing_end) for r in results]
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，返回空列表")
                return []
            raise

    async def get_confirmed_missing_ranges_async(
        self,
        symbol: str,
        interval: str,
    ) -> List[Tuple[date, date, str]]:
        """获取已确认的缺失范围（API返回空的）- 异步版本."""
        try:
            async with async_db_manager.session() as session:
                stmt = select(CompletenessCheckResult).where(
                    and_(
                        CompletenessCheckResult.symbol == symbol,
                        CompletenessCheckResult.interval == interval,
                        CompletenessCheckResult.is_confirmed_missing == True,
                    )
                )
                result = await session.execute(stmt)
                results = result.scalars().all()
                return [
                    (r.missing_start, r.missing_end, r.confirmation_reason or "UNKNOWN")
                    for r in results
                ]
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                return []
            raise

    async def confirm_missing_as_api_empty_async(
        self,
        symbol: str,
        interval: str,
        missing_start: date,
        missing_end: date,
        api_response: Optional[str] = None,
    ) -> None:
        """确认缺失是因为 API 返回空数据 - 异步版本."""
        try:
            async with async_db_manager.session() as session:
                # 更新或创建 CompletenessCheckResult
                stmt = select(CompletenessCheckResult).where(
                    and_(
                        CompletenessCheckResult.symbol == symbol,
                        CompletenessCheckResult.interval == interval,
                        CompletenessCheckResult.missing_start == missing_start,
                        CompletenessCheckResult.missing_end == missing_end,
                    )
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    existing.is_confirmed_missing = True
                    existing.confirmation_reason = "API_EMPTY"
                    existing.api_empty_checked_at = datetime.now()
                else:
                    record = CompletenessCheckResult(
                        symbol=symbol,
                        interval=interval,
                        check_start=missing_start,
                        check_end=missing_end,
                        missing_start=missing_start,
                        missing_end=missing_end,
                        is_confirmed_missing=True,
                        confirmation_reason="API_EMPTY",
                        api_empty_checked_at=datetime.now(),
                    )
                    session.add(record)

                # 同时创建 MissingDataConfirmation
                confirmation = MissingDataConfirmation(
                    symbol=symbol,
                    interval=interval,
                    missing_start=missing_start,
                    missing_end=missing_end,
                    confirmation_type="API_EMPTY",
                    api_response=api_response,
                )
                session.add(confirmation)
                await session.commit()
                logger.debug(f"{symbol}: 确认缺失 {missing_start}~{missing_end} 为 API_EMPTY")
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过确认记录")
                return
            raise

    async def confirm_missing_as_synced_async(
        self,
        symbol: str,
        interval: str,
        missing_start: date,
        missing_end: date,
    ) -> None:
        """标记缺失范围为已同步（数据已获取并保存）.

        用于防止重复 API 调用：同步成功后标记该范围已处理。
        """
        try:
            async with async_db_manager.session() as session:
                # 更新或创建 CompletenessCheckResult
                stmt = select(CompletenessCheckResult).where(
                    and_(
                        CompletenessCheckResult.symbol == symbol,
                        CompletenessCheckResult.interval == interval,
                        CompletenessCheckResult.missing_start == missing_start,
                        CompletenessCheckResult.missing_end == missing_end,
                    )
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    existing.is_confirmed_missing = True
                    existing.confirmation_reason = "SYNCED"
                else:
                    record = CompletenessCheckResult(
                        symbol=symbol,
                        interval=interval,
                        check_start=missing_start,
                        check_end=missing_end,
                        missing_start=missing_start,
                        missing_end=missing_end,
                        is_confirmed_missing=True,
                        confirmation_reason="SYNCED",
                    )
                    session.add(record)

                await session.commit()
                logger.debug(f"{symbol}: 标记范围 {missing_start}~{missing_end} 为已同步")
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过标记记录")
                return
            raise

    async def clear_resolved_missing_async(
        self,
        symbol: str,
        interval: str,
        missing_start: date,
        missing_end: date,
    ) -> None:
        """清除已修复的缺失记录 - 异步版本."""
        try:
            async with async_db_manager.session() as session:
                stmt = delete(CompletenessCheckResult).where(
                    and_(
                        CompletenessCheckResult.symbol == symbol,
                        CompletenessCheckResult.interval == interval,
                        CompletenessCheckResult.missing_start == missing_start,
                        CompletenessCheckResult.missing_end == missing_end,
                    )
                )
                await session.execute(stmt)
                await session.commit()
                logger.info(f"{symbol}: 清除已修复的缺失记录 {missing_start}~{missing_end}")
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                return
            raise

    async def is_range_confirmed_missing_async(
        self,
        symbol: str,
        interval: str,
        start_date: date,
        end_date: date,
    ) -> bool:
        """检查指定范围是否已确认为缺失（API返回空）- 异步版本."""
        try:
            async with async_db_manager.session() as session:
                stmt = select(CompletenessCheckResult).where(
                    and_(
                        CompletenessCheckResult.symbol == symbol,
                        CompletenessCheckResult.interval == interval,
                        CompletenessCheckResult.missing_start <= start_date,
                        CompletenessCheckResult.missing_end >= end_date,
                        CompletenessCheckResult.is_confirmed_missing == True,
                    )
                ).limit(1)
                result = await session.execute(stmt)
                return result.scalar() is not None
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                return False
            raise

    # ==================== 批量方法 ====================

    def batch_confirm_missing_as_api_empty(
        self,
        interval: str,
        confirmations: list[tuple[str, date, date, Optional[str]]],
    ) -> None:
        """批量确认缺失为 API 返回空（同步版本）.

        Args:
            interval: K线周期
            confirmations: [(symbol, missing_start, missing_end, api_response), ...]
        """
        if not confirmations:
            return

        symbols = list({c[0] for c in confirmations})

        try:
            with db_manager.session() as session:
                results = (
                    session.query(CompletenessCheckResult)
                    .filter(
                        and_(
                            CompletenessCheckResult.interval == interval,
                            CompletenessCheckResult.symbol.in_(symbols),
                        )
                    )
                    .all()
                )

                existing_map = {
                    (r.symbol, r.missing_start, r.missing_end): r for r in results
                }

                new_completeness: list[CompletenessCheckResult] = []
                new_confirmations: list[MissingDataConfirmation] = []
                now = datetime.now()

                for symbol, missing_start, missing_end, api_response in confirmations:
                    key = (symbol, missing_start, missing_end)
                    if key in existing_map:
                        rec = existing_map[key]
                        rec.is_confirmed_missing = True
                        rec.confirmation_reason = "API_EMPTY"
                        rec.api_empty_checked_at = now
                    else:
                        new_completeness.append(
                            CompletenessCheckResult(
                                symbol=symbol,
                                interval=interval,
                                check_start=missing_start,
                                check_end=missing_end,
                                missing_start=missing_start,
                                missing_end=missing_end,
                                is_confirmed_missing=True,
                                confirmation_reason="API_EMPTY",
                                api_empty_checked_at=now,
                            )
                        )

                    new_confirmations.append(
                        MissingDataConfirmation(
                            symbol=symbol,
                            interval=interval,
                            missing_start=missing_start,
                            missing_end=missing_end,
                            confirmation_type="API_EMPTY",
                            api_response=api_response,
                        )
                    )

                if new_completeness:
                    session.add_all(new_completeness)
                if new_confirmations:
                    session.add_all(new_confirmations)
                session.commit()
                logger.info(f"批量确认 {len(confirmations)} 个缺失范围为 API_EMPTY")
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过缺失范围批量确认")
                return
            raise

    async def batch_record_missing_ranges_async(
        self,
        interval: str,
        records: list[tuple[str, date, date, date, date]],
    ) -> None:
        """批量记录缺失范围（异步版本）.

        Args:
            interval: K线周期
            records: [(symbol, check_start, check_end, missing_start, missing_end), ...]
        """
        if not records:
            return

        symbols = list({r[0] for r in records})

        try:
            async with async_db_manager.session() as session:
                stmt = select(CompletenessCheckResult).where(
                    and_(
                        CompletenessCheckResult.interval == interval,
                        CompletenessCheckResult.symbol.in_(symbols),
                    )
                )
                result = await session.execute(stmt)
                existing = result.scalars().all()

                existing_set = {
                    (r.symbol, r.missing_start, r.missing_end) for r in existing
                }

                new_records = []
                for symbol, check_start, check_end, missing_start, missing_end in records:
                    key = (symbol, missing_start, missing_end)
                    if key not in existing_set:
                        new_records.append(
                            CompletenessCheckResult(
                                symbol=symbol,
                                interval=interval,
                                check_start=check_start,
                                check_end=check_end,
                                missing_start=missing_start,
                                missing_end=missing_end,
                            )
                        )
                        existing_set.add(key)

                if new_records:
                    session.add_all(new_records)
                    await session.commit()
                    logger.info(f"批量记录 {len(new_records)} 个缺失范围")
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过缺失范围批量记录")
                return
            raise

    async def batch_confirm_missing_as_api_empty_async(
        self,
        interval: str,
        confirmations: list[tuple[str, date, date, Optional[str]]],
    ) -> None:
        """批量确认缺失为 API 返回空（异步版本）.

        Args:
            interval: K线周期
            confirmations: [(symbol, missing_start, missing_end, api_response), ...]
        """
        if not confirmations:
            return

        symbols = list({c[0] for c in confirmations})

        try:
            async with async_db_manager.session() as session:
                stmt = select(CompletenessCheckResult).where(
                    and_(
                        CompletenessCheckResult.interval == interval,
                        CompletenessCheckResult.symbol.in_(symbols),
                    )
                )
                result = await session.execute(stmt)
                existing = result.scalars().all()

                existing_map = {
                    (r.symbol, r.missing_start, r.missing_end): r for r in existing
                }

                new_completeness: list[CompletenessCheckResult] = []
                new_confirmations: list[MissingDataConfirmation] = []
                now = datetime.now()

                for symbol, missing_start, missing_end, api_response in confirmations:
                    key = (symbol, missing_start, missing_end)
                    if key in existing_map:
                        rec = existing_map[key]
                        rec.is_confirmed_missing = True
                        rec.confirmation_reason = "API_EMPTY"
                        rec.api_empty_checked_at = now
                    else:
                        new_completeness.append(
                            CompletenessCheckResult(
                                symbol=symbol,
                                interval=interval,
                                check_start=missing_start,
                                check_end=missing_end,
                                missing_start=missing_start,
                                missing_end=missing_end,
                                is_confirmed_missing=True,
                                confirmation_reason="API_EMPTY",
                                api_empty_checked_at=now,
                            )
                        )

                    new_confirmations.append(
                        MissingDataConfirmation(
                            symbol=symbol,
                            interval=interval,
                            missing_start=missing_start,
                            missing_end=missing_end,
                            confirmation_type="API_EMPTY",
                            api_response=api_response,
                        )
                    )

                if new_completeness:
                    session.add_all(new_completeness)
                if new_confirmations:
                    session.add_all(new_confirmations)
                await session.commit()
                logger.info(f"批量确认 {len(confirmations)} 个缺失范围为 API_EMPTY")
        except RuntimeError as exc:
            if "Database not initialized" in str(exc):
                logger.debug("数据库未初始化，跳过缺失范围批量确认")
                return
            raise


# 全局实例
missing_data_tracker = MissingDataTracker()