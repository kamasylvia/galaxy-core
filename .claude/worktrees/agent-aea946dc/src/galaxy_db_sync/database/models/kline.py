"""K 线数据模型.

对应数据库 kline 表，基于 AmazingData 开发手册 4.2.6 K 线数据表定义.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, declarative_base

# 创建基础类
Base = declarative_base()


class BaseKline(Base):
    """K 线数据表基类.

    支持股票、指数、基金、期货、期权等多种品种的 K 线数据.
    对应 AmazingData 开发手册 4.2.6 K 线数据表.

    字段说明:
    - symbol: 证券代码，如 600000.SH (组合主键之一)
    - trade_time: K 线周期开始时间 (组合主键之一)
    - open: 开盘价
    - high: 最高价
    - low: 最低价
    - close: 收盘价
    - volume: 成交量
    - amount: 成交额
    """

    __abstract__ = True

    # 组合主键：证券代码 + 交易时间
    symbol: Mapped[str] = mapped_column(
        String(20), primary_key=True, comment="证券代码"
    )
    trade_time: Mapped[datetime] = mapped_column(
        DateTime, primary_key=True, comment="K 线周期开始时间"
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
        DateTime, default=datetime.utcnow, comment="创建时间"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<Kline (symbol={self.symbol}, trade_time={self.trade_time}, close={self.close})>"


# 为每个 Interval 创建单独的表
class KlineMin1(BaseKline):
    __tablename__ = "kline_min1"


class KlineMin3(BaseKline):
    __tablename__ = "kline_min3"


class KlineMin5(BaseKline):
    __tablename__ = "kline_min5"


class KlineMin10(BaseKline):
    __tablename__ = "kline_min10"


class KlineMin15(BaseKline):
    __tablename__ = "kline_min15"


class KlineMin30(BaseKline):
    __tablename__ = "kline_min30"


class KlineMin60(BaseKline):
    __tablename__ = "kline_min60"


class KlineMin120(BaseKline):
    __tablename__ = "kline_min120"


class KlineDay(BaseKline):
    __tablename__ = "kline_day"


class KlineWeek(BaseKline):
    __tablename__ = "kline_week"


class KlineMonth(BaseKline):
    __tablename__ = "kline_month"


class KlineSeason(BaseKline):
    __tablename__ = "kline_season"


class KlineYear(BaseKline):
    __tablename__ = "kline_year"


# 用于动态访问所有K线表的字典
from galaxy_db_sync.shared_kernel.enums.interval import Interval

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
