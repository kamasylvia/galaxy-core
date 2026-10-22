"""领域值对象 — Interval、SecurityType 枚举及数据类.

从 shared_kernel/enums/ 提取，删除 AmazingData 死代码 import。
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, IntEnum, StrEnum
from typing import Any


class EmptyDataReason(StrEnum):
    """空数据原因枚举."""

    DELISTED = "delisted"
    SUSPENDED = "suspended"
    API_EMPTY = "api_empty"


class Interval(Enum):
    """
    数据周期枚举 - 数据库命名
    """

    MIN1 = "min1"  # 1分钟线
    MIN3 = "min3"  # 3分钟线
    MIN5 = "min5"  # 5分钟线
    MIN10 = "min10"  # 10分钟线
    MIN15 = "min15"  # 15分钟线
    MIN30 = "min30"  # 30分钟线
    MIN60 = "min60"  # 60分钟线
    MIN120 = "min120"  # 120分钟线
    DAY = "day"  # 日线
    WEEK = "week"  # 周线
    MONTH = "month"  # 月线
    SEASON = "season"  # 季度线
    YEAR = "year"  # 年线

    @classmethod
    def from_sdk_period_value(cls, sdk_period_value: int) -> "Interval":
        """
        从AmazingData SDK的Period值创建Interval枚举

        Args:
            sdk_period_value: AmazingData SDK中Period枚举的实际值

        Returns:
            Interval: 对应的Interval枚举值
        """
        # SDK Period值到Interval的映射
        mapping = {
            10000: cls.MIN1,  # min1
            10001: cls.MIN3,  # min3
            10002: cls.MIN5,  # min5
            10003: cls.MIN10,  # min10
            10004: cls.MIN15,  # min15
            10005: cls.MIN30,  # min30
            10006: cls.MIN60,  # min60
            10007: cls.MIN120,  # min120
            10008: cls.DAY,  # day
            10009: cls.WEEK,  # week
            10010: cls.MONTH,  # month
            10011: cls.SEASON,  # season
            10012: cls.YEAR,  # year
        }

        if sdk_period_value in mapping:
            return mapping[sdk_period_value]

        raise ValueError(
            f"No matching Interval enum found for SDK Period value: {sdk_period_value}"
        )

    def to_sdk_period_value(self) -> int:
        """
        将Interval枚举转换为AmazingData SDK的Period值

        Returns:
            int: 对应的AmazingData SDK中Period枚举的实际值
        """
        # Interval到SDK Period值的映射
        mapping = {
            Interval.MIN1: 10000,  # min1
            Interval.MIN3: 10001,  # min3
            Interval.MIN5: 10002,  # min5
            Interval.MIN10: 10003,  # min10
            Interval.MIN15: 10004,  # min15
            Interval.MIN30: 10005,  # min30
            Interval.MIN60: 10006,  # min60
            Interval.MIN120: 10007,  # min120
            Interval.DAY: 10008,  # day
            Interval.WEEK: 10009,  # week
            Interval.MONTH: 10010,  # month
            Interval.SEASON: 10011,  # season
            Interval.YEAR: 10012,  # year
        }

        if self in mapping:
            return mapping[self]

        raise ValueError(f"No matching SDK Period value found for Interval: {self}")

    @classmethod
    def from_value(cls, value: int | str) -> "Interval":
        """
        从数值创建Interval枚举

        Args:
            value: 数值

        Returns:
            Interval: 对应的Interval枚举值
        """
        if isinstance(value, int):
            value = str(value)

        for interval in cls:
            if interval.value == value:
                return interval

        raise ValueError(f"No Interval enum found for value: {value}")

    @classmethod
    def from_period_name(cls, period_name: str) -> "Interval":
        """
        从AmazingData SDK的Period枚举名称创建Interval枚举

        Args:
            period_name: AmazingData SDK的Period枚举名称，如 'min1', 'day' 等

        Returns:
            Interval: 对应的Interval枚举值
        """
        # 将输入的名称转换为大写以匹配Interval枚举
        period_name_lower = period_name.lower()
        try:
            # 直接使用lowercase名称查找Interval枚举
            return cls(period_name_lower)
        except ValueError:
            raise ValueError(f"No Interval enum found for period name: {period_name}")

    def to_period_name(self) -> str:
        """
        获取对应的AmazingData SDK的Period枚举名称

        Returns:
            str: AmazingData SDK的Period枚举名称
        """
        return self.value  # 返回枚举的字符串值，如 'day', 'min1' 等


# =====================================================================
# 证券类型枚举
# =====================================================================


class SecurityType(StrEnum):
    """代码类型security_type(沪深北) - AmazingData API原始枚举"""

    EXTRA_STOCK_A = "EXTRA_STOCK_A"
    """上交所A股、深交所A股和北交所的股票列表"""

    SH_A = "SH_A"
    """上交所A股的股票列表"""

    SZ_A = "SZ_A"
    """深交所A股的股票列表"""

    BJ_A = "BJ_A"
    """北交所的股票列表"""

    EXTRA_STOCK_A_SH_SZ = "EXTRA_STOCK_A_SH_SZ"
    """上交所A股和深交所A股的股票列表"""

    EXTRA_INDEX_A_SH_SZ = "EXTRA_INDEX_A_SH_SZ"
    """上交所和深交所指数列表"""

    EXTRA_INDEX_A = "EXTRA_INDEX_A"
    """上交所、深交所和北交所的指数列表"""

    SH_INDEX = "SH_INDEX"
    """上交所指数列表"""

    SZ_INDEX = "SZ_INDEX"
    """深交所指数列表"""

    BJ_INDEX = "BJ_INDEX"
    """北交所的指数列表"""

    SH_ETF = "SH_ETF"
    """上交所的ETF列表"""

    SZ_ETF = "SZ_ETF"
    """深交所的ETF列表"""

    EXTRA_ETF = "EXTRA_ETF"
    """上交所、深交所的ETF列表"""

    SH_KZZ = "SH_KZZ"
    """上交所的可转债列表"""

    SZ_KZZ = "SZ_KZZ"
    """深交所的可转债列表"""

    EXTRA_KZZ = "EXTRA_KZZ"
    """上交所、深交所的可转债列表"""

    SH_HKT = "SH_HKT"
    """沪港通"""

    SZ_HKT = "SZ_HKT"
    """深港通"""

    EXTRA_HKT = "EXTRA_HKT"
    """沪深港通"""

    SH_GLRA = "SH_GLRA"
    """上交所逆回购"""

    SZ_GLRA = "SZ_GLRA"
    """深交所逆回购"""

    EXTRA_GLRA = "EXTRA_GLRA"
    """沪深逆回购"""


class SecurityTypeFuture(StrEnum):
    """代码类型security_type(期货交易所) - AmazingData API原始枚举"""

    EXTRA_FUTURE = "EXTRA_FUTURE"
    """期货, 包含中金所/上期所/大商所/郑商所/上海国际能源交易中心所"""

    ZJ_FUTURE = "ZJ_FUTURE"
    """期货, 包含中金所"""

    SQ_FUTURE = "SQ_FUTURE"
    """期货, 包含上期所"""

    DS_FUTURE = "DS_FUTURE"
    """期货, 包含大商所"""

    ZS_FUTURE = "ZS_FUTURE"
    """期货, 包含郑商所"""

    SN_FUTURE = "SN_FUTURE"
    """期货, 包含上海国际能源交易中心所"""


class SecurityTypeOption(StrEnum):
    """代码类型security_type(期权) - AmazingData API原始枚举"""

    EXTRA_ETF_OP = "EXTRA_ETF_OP"
    """ETF期权, 上交所/深交所"""

    SH_OPTION = "SH_OPTION"
    """ETF期权, 包含上交所"""

    SZ_OPTION = "SZ_OPTION"
    """ETF期权, 包含深交所"""


# =====================================================================
# Domain 值对象（dataclass）
# =====================================================================


@dataclass
class KlineBar:
    """K线数据条目."""

    symbol: str
    trade_time: datetime
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int | None
    amount: float | None
    security_type: SecurityType
    is_final: bool = True


@dataclass
class StockInfo:
    """证券列表条目（从 get_stock_list 返回）."""

    symbol: str
    list_date: str | None


@dataclass
class StockBasic:
    """证券基础信息（从 get_stock_basic 返回）."""

    symbol: str
    security_type: SecurityType
    list_date: str | None
    delist_date: str | None
    stock_name: str | None
    market: str | None
    exchange: str | None


@dataclass
class BackwardFactor:
    """复权因子（从 get_backward_factor 返回）.

    trade_time: 北京时区 aware datetime(timestamptz 列需要)。
    """

    symbol: str
    trade_time: datetime
    backward_factor: float


# =====================================================================
# 财务数据枚举与值对象
# =====================================================================


class FinancialDataType(StrEnum):
    """财务数据类型枚举 — 对应 6 个 InfoData API 接口."""

    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW = "cash_flow"
    INCOME = "income"
    PROFIT_EXPRESS = "profit_express"
    PROFIT_NOTICE = "profit_notice"
    DIVIDEND = "dividend"


class ReportType(IntEnum):
    """报告期类型 — 对应 API 的 REPORT_TYPE 字段（D-14）."""

    Q1 = 1  # 3月（第一季度）
    H1 = 2  # 6月（半年度）
    Q3 = 3  # 9月（第三季度）
    ANNUAL = 4  # 12月（年度）


@dataclass
class FinancialRecord:
    """财务数据记录 — 统一的财务数据载体.

    三大报表（balance_sheet / cash_flow / income）具有 statement_type，
    业绩快报（profit_express）和业绩预告（profit_notice）的 statement_type 为 None。

    fields 为动态字段容器，保存 API 返回的全部财务字段（由 adapter 层完成
    API 大写 → snake_case 映射）。
    """

    symbol: str
    reporting_period: str  # YYYYMMDD 格式，如 "20240331"
    statement_type: str | None  # 三大报表有值，快报/预告为 None
    ann_date: str | None  # 公告日期（profit_notice 用作 PK 的一部分）
    actual_ann_date: str | None  # 实际公告日期
    data_type: FinancialDataType
    fields: dict[str, Any]  # 动态字段容器


@dataclass
class FinancialSyncResult:
    """财务数据同步结果."""

    total_symbols: int = 0
    success_count: int = 0
    synced_records: int = 0
    failed_codes: list[str] = field(default_factory=list)


# =====================================================================
# 指数数据值对象（交易所指数 + 行业指数，对应 3.5.12 / 3.5.13 接口）
# =====================================================================


@dataclass
class IndexConstituent:
    """交易所指数成分股条目 — 对应 get_index_constituent.

    成分股是慢变维度，纳/剔日期决定一条记录的生命周期。
    """

    index_code: str
    con_code: str
    in_date: str | None  # 纳入日期 YYYYMMDD
    out_date: str | None  # 剔除日期 YYYYMMDD（未剔除为 None）
    index_name: str | None


@dataclass
class IndexWeight:
    """交易所指数成分股日权重 — 对应 get_index_weight.

    SDK 仅支持 5 个指数（上证50/沪深300/中证500/中证800/中证1000）。
    """

    index_code: str
    con_code: str
    trade_date: str  # YYYYMMDD
    total_share: float | None
    free_share_ratio: float | None
    calc_share: float | None
    weight_factor: float | None
    weight: float | None
    close: float | None


@dataclass
class IndustryBaseInfo:
    """行业指数基本信息条目 — 对应 get_industry_base_info（纯目录数据）."""

    index_code: str
    industry_code: str
    level_type: int | None  # 1=一级行业 2=二级 3=三级
    level1_name: str | None
    level2_name: str | None
    level3_name: str | None
    is_pub: int | None  # 1=已发布 2=未发布
    change_reason: str | None


@dataclass
class IndustryConstituent:
    """行业指数成分股条目 — 对应 get_industry_constituent.

    schema 与 IndexConstituent 相同，但来源/语义不同，分表存储。
    """

    index_code: str
    con_code: str
    in_date: str | None
    out_date: str | None
    index_name: str | None


@dataclass
class IndustryWeight:
    """行业指数成分股日权重 — 对应 get_industry_weight.

    字段比 IndexWeight 精简（仅 4 字段），但量级大（覆盖全行业）。
    """

    index_code: str
    con_code: str
    trade_date: str  # YYYYMMDD
    weight: float | None


@dataclass
class IndustryDaily:
    """行业指数日行情 — 对应 get_industry_daily.

    行业指数唯一行情源（不通过 query_kline），含 PB/PE/市值等估值字段。
    """

    index_code: str
    trade_date: str  # YYYYMMDD
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    pre_close: float | None
    volume: float | None
    amount: float | None
    pb: float | None  # 指数市净率
    pe: float | None  # 指数市盈率
    total_cap: float | None  # 总市值（万元）
    a_float_cap: float | None  # A股流通市值（万元）


# =============================================================================
# Phase 02 — 多数据源资金流向数据层(2026-06-19 范围修订:12→5 dataclass)
# 总纲收敛为「跟着主力选行业」, 启用 5 张表:
#   akshare sector_fund_flow ×1 + AmazingData long_hu_bang/block_trading/margin_summary/margin_detail ×4
# baostock 整源(3 VO)+ akshare stock/north/market/industry_pe(4 VO)已删, 未启用不建表。
# 字段顺序:PK 必填 str 在前,可选标识符居中,数值指标 float | None 在后。
# 日期字段统一 str YYYYMMDD(store adapter 的 _yyyymmdd_to_date 转 Date)。
# =============================================================================


# -----------------------------------------------------------------------------
# akshare × 1(对应 FundFlowProviderPort akshare 侧)
# -----------------------------------------------------------------------------


@dataclass
class AkshareSectorFundFlow:
    """板块资金流 — 对应 get_sector_fund_flow + 表 akshare_sector_fund_flow_daily.

    仅当日快照(RESEARCH §A10 caveat — scheduler 日度累积建库)。
    """

    trade_date: str  # YYYYMMDD
    sector_type: str  # 行业/概念/地域
    sector_name: str
    main_net_amount: float | None
    main_net_pct: float | None
    super_large_net_amount: float | None
    super_large_net_pct: float | None
    large_net_amount: float | None
    large_net_pct: float | None
    medium_net_amount: float | None
    medium_net_pct: float | None
    small_net_amount: float | None
    small_net_pct: float | None
    top_stock: str | None  # 主力净流入最大股


# -----------------------------------------------------------------------------
# AmazingData × 4(对应 FundFlowProviderPort amazingdata 侧)
# 字段名已是 snake_case 化的大写 API 字段(MARKET_CODE→market_code 等)。
# -----------------------------------------------------------------------------


@dataclass
class LongHuBang:
    """龙虎榜明细 — 对应 get_long_hu_bang + 表 long_hu_bang.

    机构/游资席位买卖,flow_mark 区分买/卖方向。
    """

    market_code: str
    trade_date: str  # YYYYMMDD
    security_name: str | None
    reason_type: str | None  # 入榜原因代码
    reason_type_name: str | None  # 入榜原因名称(REASON_TYPE_NAME,避免数据丢失)
    change_range: float | None  # 涨跌幅
    trader_name: str  # 席位名
    flow_mark: int  # 1=买/2=卖(整型标记,与 PLAN-03 model Mapped[int] PK 对齐)
    buy_amount: float | None
    sell_amount: float | None
    total_amount: float | None
    total_volume: float | None


@dataclass
class BlockTrading:
    """大宗交易 — 对应 get_block_trading + 表 block_trading.

    b_ 前缀沿用 API 原始字段名 snake_case 化。
    """

    market_code: str
    trade_date: str  # YYYYMMDD
    b_share_price: float | None  # 成交价
    b_share_volume: float | None  # 成交量(万股)
    b_frequency: int | None  # 笔数(整型计数,与 PLAN-03 model Mapped[int | None] 对齐)
    block_avg_volume: float | None  # 每笔均量
    b_share_amount: float | None  # 成交金额(万元)
    b_buyer_name: str  # 买方营业部
    b_seller_name: str  # 卖方营业部


@dataclass
class MarginSummary:
    """两融汇总 — 对应 get_margin_summary + 表 margin_summary_daily.

    全市场每日 1 行汇总。
    """

    trade_date: str  # YYYYMMDD
    sum_borrow_money_balance: float | None  # 融资余额
    sum_purch_with_borrow_money: float | None  # 融资买入额
    sum_repayment_of_borrow_money: float | None  # 融资偿还额
    sum_sec_lending_balance: float | None  # 融券余额
    sum_sales_of_borrowed_sec: float | None  # 融券卖出量
    sum_margin_trade_balance: float | None  # 融资融券余额


@dataclass
class MarginDetail:
    """两融明细 — 对应 get_margin_detail(dict value 行结构) + 表 margin_detail_daily.

    per 标的券,对应 get_margin_detail 返回 dict 的 value DataFrame 行结构。
    """

    market_code: str
    trade_date: str  # YYYYMMDD
    security_name: str | None
    borrow_money_balance: float | None  # 融资余额
    purch_with_borrow_money: float | None  # 融资买入额
    repayment_of_borrow_money: float | None  # 融资偿还额
    sec_lending_balance: float | None  # 融券余额
    sales_of_borrowed_sec: float | None  # 融券卖出量
    repayment_of_borrow_sec: float | None  # 融券偿还量
    sec_lending_balance_vol: float | None  # 融券余量
    margin_trade_balance: float | None  # 融资融券余额
