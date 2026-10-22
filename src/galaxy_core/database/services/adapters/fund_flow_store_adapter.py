"""AmazingData 资金流向存储适配器.

将 LongHuBang / BlockTrading / MarginSummary / MarginDetail 值对象 UPSERT
到对应表。复用 industry_index_store_adapter 模式。
"""

import logging
from dataclasses import asdict
from datetime import date

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.database.models.fund_flow_data import (
    BlockTrading,
    LongHuBang,
    MarginDetailDaily,
    MarginSummaryDaily,
)
from galaxy_core.domain.value_objects import (
    BlockTrading as BlockTradingVO,
)
from galaxy_core.domain.value_objects import (
    LongHuBang as LongHuBangVO,
)
from galaxy_core.domain.value_objects import (
    MarginDetail,
    MarginSummary,
)
from galaxy_core.shared_kernel.exceptions import CacheError
from galaxy_core.shared_kernel.nocodb_schema import NOCODB_SYSTEM_COLUMNS
from galaxy_core.shared_kernel.utils.config_loader import get_config

logger = logging.getLogger(__name__)

_LONGHU_CONFLICT = ["market_code", "trade_date", "trader_name", "flow_mark"]
_BLOCK_CONFLICT = ["market_code", "trade_date", "b_buyer_name", "b_seller_name"]
_MARGIN_SUMMARY_CONFLICT = ["trade_date"]
_MARGIN_DETAIL_CONFLICT = ["market_code", "trade_date"]


def _yyyymmdd_to_date(value: str | None) -> date | None:
    """YYYYMMDD 字符串 → date(nocodb 形态 trade_date=date 列)."""
    if value is None:
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError, IndexError:
        return None


class FundFlowStoreAdapter:
    """AmazingData 龙虎榜/大宗/两融 UPSERT."""

    def __init__(self, db_manager: AsyncDatabaseManager) -> None:
        self._db = db_manager

    async def save_long_hu_bang(self, records: list[LongHuBangVO]) -> int:
        """UPSERT 龙虎榜. 冲突键: (market_code, trade_date, trader_name, flow_mark)."""
        if not records:
            return 0
        data_list = [asdict(r) for r in records]
        converted = self._convert_trade_date(data_list)
        return await self._upsert(LongHuBang, _LONGHU_CONFLICT, converted)

    async def save_block_trading(self, records: list[BlockTradingVO]) -> int:
        """UPSERT 大宗交易. 冲突键: (market_code, trade_date, b_buyer_name, b_seller_name)."""
        if not records:
            return 0
        data_list = [asdict(r) for r in records]
        converted = self._convert_trade_date(data_list)
        return await self._upsert(BlockTrading, _BLOCK_CONFLICT, converted)

    async def save_margin_summary(self, records: list[MarginSummary]) -> int:
        """UPSERT 两融汇总. 冲突键: (trade_date)."""
        if not records:
            return 0
        data_list = [asdict(r) for r in records]
        converted = self._convert_trade_date(data_list)
        return await self._upsert(MarginSummaryDaily, _MARGIN_SUMMARY_CONFLICT, converted)

    async def save_margin_detail(self, records: list[MarginDetail]) -> int:
        """UPSERT 两融明细. 冲突键: (market_code, trade_date)."""
        if not records:
            return 0
        data_list = [asdict(r) for r in records]
        converted = self._convert_trade_date(data_list)
        return await self._upsert(MarginDetailDaily, _MARGIN_DETAIL_CONFLICT, converted)

    @staticmethod
    def _convert_trade_date(data_list: list[dict]) -> list[dict]:
        """批量转 trade_date YYYYMMDD → date,跳过无效行."""
        converted = []
        for d in data_list:
            td = _yyyymmdd_to_date(d.get("trade_date"))
            if td is None:
                continue
            d["trade_date"] = td
            converted.append(d)
        return converted

    async def _upsert(self, model, conflict_cols: list[str], data_list: list[dict]) -> int:
        """通用批处理 UPSERT(复制 industry_index_store_adapter.py:138-177)."""
        if not data_list:
            return 0

        # nocodb 形态:date/boolean/文本列统一强转(如 龙虎榜.flow_mark int→text)
        from galaxy_core.shared_kernel.nocodb_schema import coerce_nocodb_columns

        data_list = coerce_nocodb_columns(model, data_list)

        seen: dict[tuple, dict] = {}
        for row in data_list:
            key = tuple(row.get(c) for c in conflict_cols)
            seen[key] = row
        data_list = list(seen.values())

        batch_size = get_config("sync.batch", "db_upsert", 100)
        if not isinstance(batch_size, int):
            batch_size = 100

        try:
            async with self._db.session() as session:
                for i in range(0, len(data_list), batch_size):
                    batch = data_list[i : i + batch_size]
                    stmt = pg_insert(model).values(batch)
                    update_dict = {
                        col.name: stmt.excluded[col.name]
                        for col in model.__table__.columns
                        if col.name not in conflict_cols and col.name not in NOCODB_SYSTEM_COLUMNS
                    }
                    # nocodb 审计:冲突更新分支刷新 updated_at(出站增量 watermark 用;
                    # INSERT 分支由 DB DEFAULT now() 填充)
                    update_dict["updated_at"] = func.now()
                    upsert_stmt = stmt.on_conflict_do_update(
                        index_elements=conflict_cols,
                        set_=update_dict,
                    )
                    await session.execute(upsert_stmt)
        except SQLAlchemyError as e:
            raise CacheError(
                message=f"保存 fund_flow 数据失败: {e}",
                operation="save_fund_flow_data",
                key=f"{model.__tablename__}:{len(data_list)}条",
            ) from e

        logger.debug(f"保存 {len(data_list)} 条 {model.__tablename__} 记录")
        return len(data_list)
