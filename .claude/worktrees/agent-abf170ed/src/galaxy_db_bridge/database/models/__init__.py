"""PostgreSQL 数据模型模块.

包含所有数据库存储相关的 SQLAlchemy ORM 模型。
"""

# 从本地导入 Kline 模型 - 现在是分表结构
from galaxy_db_bridge.database.models.kline import (
    Base,
    BaseKline,
    KlineMin1,
    KlineMin3,
    KlineMin5,
    KlineMin10,
    KlineMin15,
    KlineMin30,
    KlineMin60,
    KlineMin120,
    KlineDay,
    KlineWeek,
    KlineMonth,
    KlineSeason,
    KlineYear,
    INTERVAL_MODEL_MAP,
)

__all__ = [
    # Base
    "Base",
    # Market Data
    "BaseKline",
    "KlineMin1",
    "KlineMin3",
    "KlineMin5",
    "KlineMin10",
    "KlineMin15",
    "KlineMin30",
    "KlineMin60",
    "KlineMin120",
    "KlineDay",
    "KlineWeek",
    "KlineMonth",
    "KlineSeason",
    "KlineYear",
    "INTERVAL_MODEL_MAP",
]
