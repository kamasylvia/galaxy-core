"""通用 last_sync_date 读写(Phase 1&2 表增量用).

走 last_sync_date 表的 (sync_type, scope_key) 模式,与 kline(symbol, interval)/
financial(symbol, data_type) 模式并列(见 03-02-PLAN)。

scope_key=None 表示全市场汇总表(如 margin_summary)— get 用 IS NULL 匹配,
set UPSERT 时 NULL 不参与唯一约束(PostgreSQL 语义),单行无冲突。
"""

import logging
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import func

from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.database.models.last_sync_date import LastSyncDate
from galaxy_core.shared_kernel.exceptions import CacheError

logger = logging.getLogger(__name__)


class LastSyncDateStore:
    """last_sync_date 表 (sync_type, scope_key) 模式读写."""

    def __init__(self, db_manager: AsyncDatabaseManager) -> None:
        self._db = db_manager

    async def get_last_sync_date(
        self, sync_type: str, scope_key: str | None
    ) -> date | None:
        """查最后同步日。

        Args:
            sync_type: 数据类标识(index_weight/long_hu_bang/...)
            scope_key: natural key(index_code/market_code/channel);全市场汇总表传 None

        Returns:
            date | None:无记录返 None(空表首次,调用方据此走 first_sync_date)
        """
        try:
            async with self._db.session() as session:
                stmt = select(LastSyncDate.last_sync_date).where(
                    LastSyncDate.sync_type == sync_type
                )
                if scope_key is None:
                    stmt = stmt.where(LastSyncDate.scope_key.is_(None))
                else:
                    stmt = stmt.where(LastSyncDate.scope_key == scope_key)
                result = await session.execute(stmt)
                row = result.first()
                return row[0] if row else None
        except SQLAlchemyError as e:
            raise CacheError(
                message=f"读取 last_sync_date 失败(sync_type={sync_type}, scope_key={scope_key}): {e}",
                operation="get_last_sync_date",
                key=f"{sync_type}:{scope_key}",
            ) from e

    async def get_last_sync_dates_batch(
        self, sync_type: str, scope_keys: list[str]
    ) -> dict[str, date]:
        """批量查多个 scope_key 的最后同步日(2026-08-01 新增)。

        单 SQL 查询替代 N 次 get_last_sync_date,消除 fundflow per-symbol 表
        (long_hu_bang/block_trading/margin_detail)5200+ 次串行查询开销。

        Args:
            sync_type: 数据类标识
            scope_keys: scope_key 列表(market_code)

        Returns:
            {scope_key: date} 字典,无记录的 key 不包含在内。
        """
        if not scope_keys:
            return {}
        try:
            async with self._db.session() as session:
                stmt = select(
                    LastSyncDate.scope_key, LastSyncDate.last_sync_date
                ).where(
                    LastSyncDate.sync_type == sync_type,
                    LastSyncDate.scope_key.in_(scope_keys),
                )
                result = await session.execute(stmt)
                return {row[0]: row[1] for row in result.all()}
        except SQLAlchemyError as e:
            raise CacheError(
                message=(
                    f"批量读取 last_sync_date 失败(sync_type={sync_type}, "
                    f"{len(scope_keys)} keys): {e}"
                ),
                operation="get_last_sync_dates_batch",
                key=f"{sync_type}:{len(scope_keys)}keys",
            ) from e

    async def set_last_sync_date(
        self, sync_type: str, scope_key: str | None, last_date: date
    ) -> None:
        """UPSERT 最后同步日。

        D-24(2026-06-20):scope_key=NULL 走 partial unique index
        `uq_last_sync_date_sync_type_global`(WHERE scope_key IS NULL);
        scope_key≠NULL 走 `uq_last_sync_date_sync_type_scoped`。
        on_conflict 需指定对应 index + WHERE 子句匹配 partial index。

        空记录场景由调用方判断不调此方法(D-08 — 空响应不推进 last_sync_date)。
        """
        try:
            async with self._db.session() as session:
                stmt = pg_insert(LastSyncDate).values(
                    symbol=None,
                    interval=None,
                    data_type=None,
                    sync_type=sync_type,
                    scope_key=scope_key,
                    last_sync_date=last_date,
                )
                if scope_key is None:
                    # 全局表:匹配 partial index(WHERE scope_key IS NULL)
                    upsert_stmt = stmt.on_conflict_do_update(
                        index_elements=["sync_type"],
                        index_where=text("scope_key IS NULL"),
                        set_={
                            "last_sync_date": stmt.excluded.last_sync_date,
                            "updated_at": func.now(),
                        },
                    )
                else:
                    # per-symbol 表:匹配 partial index(WHERE scope_key IS NOT NULL)
                    upsert_stmt = stmt.on_conflict_do_update(
                        index_elements=["sync_type", "scope_key"],
                        index_where=text("scope_key IS NOT NULL"),
                        set_={
                            "last_sync_date": stmt.excluded.last_sync_date,
                            "updated_at": func.now(),
                        },
                    )
                await session.execute(upsert_stmt)
        except SQLAlchemyError as e:
            raise CacheError(
                message=f"写入 last_sync_date 失败(sync_type={sync_type}, scope_key={scope_key}): {e}",
                operation="set_last_sync_date",
                key=f"{sync_type}:{scope_key}",
            ) from e
