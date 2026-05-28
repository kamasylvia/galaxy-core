"""K 线数据模型.

对应数据库 kline 表，基于 AmazingData 开发手册 4.2.6 K 线数据表定义.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, declarative_base

# 创建基础类
Base = declarative_base()


class BaseKline(Base):
    """K 线数据表基类.

    支持股票、指数、基金、期货、期权等多种品种的 K 线数据.
    对应 AmazingData 开发手册 4.2.6 K 线数据表.

    字段说明:
    - id: 主键，使用顺序 UUID
    - symbol: 证券代码，如 600000.SH
    - start_time: K 线周期开始时间
    - interval: K 线周期 (min1/min5/min15/min30/min60/min120/day/week/month/season/year)
    - open: 开盘价
    - high: 最高价
    - low: 最低价
    - close: 收盘价
    - volume: 成交量
    - amount: 成交额
    """

    __abstract__ = True

    # 主键：使用自增整数
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="主键 ID",
    )

    # 证券标识
    symbol: Mapped[str] = mapped_column(String(20), comment="证券代码", index=True)
    trade_time: Mapped[datetime] = mapped_column(
        DateTime, comment="K 线周期开始时间", index=True
    )

    # OHLCV 数据
    open: Mapped[float] = mapped_column(Float, comment="开盘价")
    high: Mapped[float] = mapped_column(Float, comment="最高价")
    low: Mapped[float] = mapped_column(Float, comment="最低价")
    close: Mapped[float] = mapped_column(Float, comment="收盘价")
    volume: Mapped[int] = mapped_column(BigInteger, comment="成交量")
    amount: Mapped[Optional[float]] = mapped_column(Float, comment="成交额")

    # 品种类型
    security_type: Mapped[Optional[str]] = mapped_column(String(20), comment="品种类型")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), comment="创建时间"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<Kline (symbol={self.symbol}, trade_time={self.trade_time}, close={self.close})>"


# 为每个 Interval 创建单独的表
class KlineMin1(BaseKline):
    __tablename__ = "kline_min1"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trade_time",
            name="uq_kline_min1_symbol_time",
        ),
        Index("idx_kline_min1_symbol", "symbol"),
        Index("idx_kline_min1_trade_time", "trade_time"),
    )


class KlineMin3(BaseKline):
    __tablename__ = "kline_min3"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trade_time",
            name="uq_kline_min3_symbol_time",
        ),
        Index("idx_kline_min3_symbol", "symbol"),
        Index("idx_kline_min3_trade_time", "trade_time"),
    )


class KlineMin5(BaseKline):
    __tablename__ = "kline_min5"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trade_time",
            name="uq_kline_min5_symbol_time",
        ),
        Index("idx_kline_min5_symbol", "symbol"),
        Index("idx_kline_min5_trade_time", "trade_time"),
    )


class KlineMin10(BaseKline):
    __tablename__ = "kline_min10"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trade_time",
            name="uq_kline_min10_symbol_time",
        ),
        Index("idx_kline_min10_symbol", "symbol"),
        Index("idx_kline_min10_trade_time", "trade_time"),
    )


class KlineMin15(BaseKline):
    __tablename__ = "kline_min15"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trade_time",
            name="uq_kline_min15_symbol_time",
        ),
        Index("idx_kline_min15_symbol", "symbol"),
        Index("idx_kline_min15_trade_time", "trade_time"),
    )


class KlineMin30(BaseKline):
    __tablename__ = "kline_min30"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trade_time",
            name="uq_kline_min30_symbol_time",
        ),
        Index("idx_kline_min30_symbol", "symbol"),
        Index("idx_kline_min30_trade_time", "trade_time"),
    )


class KlineMin60(BaseKline):
    __tablename__ = "kline_min60"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trade_time",
            name="uq_kline_min60_symbol_time",
        ),
        Index("idx_kline_min60_symbol", "symbol"),
        Index("idx_kline_min60_trade_time", "trade_time"),
    )


class KlineMin120(BaseKline):
    __tablename__ = "kline_min120"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trade_time",
            name="uq_kline_min120_symbol_time",
        ),
        Index("idx_kline_min120_symbol", "symbol"),
        Index("idx_kline_min120_trade_time", "trade_time"),
    )


class KlineDay(BaseKline):
    __tablename__ = "kline_day"

    __table_args__ = (
        UniqueConstraint("symbol", "trade_time", name="uq_kline_day_symbol_time"),
        Index("idx_kline_day_symbol", "symbol"),
        Index("idx_kline_day_trade_time", "trade_time"),
    )


class KlineWeek(BaseKline):
    __tablename__ = "kline_week"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trade_time",
            name="uq_kline_week_symbol_time",
        ),
        Index("idx_kline_week_symbol", "symbol"),
        Index("idx_kline_week_trade_time", "trade_time"),
    )


class KlineMonth(BaseKline):
    __tablename__ = "kline_month"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trade_time",
            name="uq_kline_month_symbol_time",
        ),
        Index("idx_kline_month_symbol", "symbol"),
        Index("idx_kline_month_trade_time", "trade_time"),
    )


class KlineSeason(BaseKline):
    __tablename__ = "kline_season"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trade_time",
            name="uq_kline_season_symbol_time",
        ),
        Index("idx_kline_season_symbol", "symbol"),
        Index("idx_kline_season_trade_time", "trade_time"),
    )


class KlineYear(BaseKline):
    __tablename__ = "kline_year"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trade_time",
            name="uq_kline_year_symbol_time",
        ),
        Index("idx_kline_year_symbol", "symbol"),
        Index("idx_kline_year_trade_time", "trade_time"),
    )


# 用于动态访问所有K线表的字典
from galaxy_db_bridge.shared_kernel.enums.interval import Interval

INTERVAL_MODEL_MAP = {
    Interval.MIN1.value: KlineMin1,
    Interval.MIN3.value: KlineMin3,
    Interval.MIN5.value: KlineMin5,
    Interval.MIN10.value: KlineMin10,
    Interval.MIN15.value: KlineMin15,
    Interval.MIN30.value: KlineMin30,
    Interval.MIN60.value: KlineMin60,
    Interval.MIN120.value: KlineMin120,
    Interval.DAY.value: KlineDay,
    Interval.WEEK.value: KlineWeek,
    Interval.MONTH.value: KlineMonth,
    Interval.SEASON.value: KlineSeason,
    Interval.YEAR.value: KlineYear,
}
