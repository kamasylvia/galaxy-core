"""PostgreSQL 数据模型模块.

包含所有数据库存储相关的 SQLAlchemy ORM 模型。

Phase 02(2026-06-19 范围修订,见 02-SCOPE-REVISION-REPORT.md):
总纲收敛为「跟着主力选行业」, 启用 5 张表 — akshare 板块资金流 + AmazingData 龙虎榜/大宗/两融。
baostock 整源 + akshare 个股/北向/大盘/行业 PE 已删, 未启用表不建表。
"""

# 从本地导入 Kline 模型 - 现在是分表结构
from galaxy_core.database.models.akshare_data import AkshareSectorFundFlowDaily
from galaxy_core.database.models.backward_factor import BackwardFactor
from galaxy_core.database.models.financial_data import (
    BalanceSheet,
    CashFlow,
    Income,
    ProfitExpress,
    ProfitNotice,
)
from galaxy_core.database.models.fund_flow_data import (
    BlockTrading,
    LongHuBang,
    MarginDetailDaily,
    MarginSummaryDaily,
)
from galaxy_core.database.models.index_data import (
    IndexConstituent,
    IndexWeight,
    IndustryBaseInfo,
    IndustryConstituent,
    IndustryDaily,
    IndustryWeight,
)
from galaxy_core.database.models.kline import (
    INTERVAL_MODEL_MAP,
    Base,
    BaseKline,
    BaseKlineMinute,
    KlineDay,
    KlineMin1,
    KlineMin3,
    KlineMin5,
    KlineMin10,
    KlineMin15,
    KlineMin30,
    KlineMin60,
    KlineMin120,
    KlineMonth,
    KlineSeason,
    KlineWeek,
    KlineYear,
)
from galaxy_core.database.models.last_sync_date import LastSyncDate
from galaxy_core.database.models.stock_basic import StockBasic
from galaxy_core.database.models.sync_state import SyncState
from galaxy_core.database.models.trading_calendar import TradingCalendar

__all__ = [
    # Base
    "Base",
    # Market Data
    "BaseKline",
    "BaseKlineMinute",
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
    # Sync State
    "SyncState",
    # P0 Data
    "StockBasic",
    "BackwardFactor",
    # Trading Calendar
    "TradingCalendar",
    # Sync Tracking
    "LastSyncDate",
    # Financial Data
    "BalanceSheet",
    "CashFlow",
    "Income",
    "ProfitExpress",
    "ProfitNotice",
    # Index Data (Exchange + Industry)
    "IndexConstituent",
    "IndexWeight",
    "IndustryBaseInfo",
    "IndustryConstituent",
    "IndustryDaily",
    "IndustryWeight",
    # Phase 02 — Akshare Fund Flow (scope-revised: 5→1)
    "AkshareSectorFundFlowDaily",
    # Phase 02 — AmazingData Fund Flow
    "LongHuBang",
    "BlockTrading",
    "MarginSummaryDaily",
    "MarginDetailDaily",
]
