"""PostgreSQL 数据模型模块.

包含所有数据库存储相关的 SQLAlchemy ORM 模型。
"""

# 从本地导入 Kline 模型 - 现在是分表结构
from galaxy_db_sync.database.models.kline import (
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
from galaxy_db_sync.database.models.empty_query_result import EmptyQueryResult
from galaxy_db_sync.database.models.sync_state import SyncState
from galaxy_db_sync.database.models.completeness_check_log import CompletenessCheckLog
from galaxy_db_sync.database.models.completeness_check_result import (
    CompletenessCheckResult,
    MissingDataConfirmation,
)
from galaxy_db_sync.database.models.stock_basic import StockBasic
from galaxy_db_sync.database.models.stock_status import StockStatus
from galaxy_db_sync.database.models.backward_factor import BackwardFactor
from galaxy_db_sync.database.models.trading_calendar import TradingCalendar

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
    # Query Result Cache
    "EmptyQueryResult",
    # Sync State
    "SyncState",
    # Completeness Check
    "CompletenessCheckLog",
    "CompletenessCheckResult",
    "MissingDataConfirmation",
    # P0 Data
    "StockBasic",
    "StockStatus",
    "BackwardFactor",
    # Trading Calendar
    "TradingCalendar",
]
