"""K 线数据模型(nocodb 形态,2026-08-26 回迁).

表名=nocodb 中文表名;业务列名=原 pg 列名。
长 K(日/周/月/季/年)trade_time = Date(北京日期);
分钟 K trade_time = naive DateTime(北京 wall-clock,无 tz)。
数值列 = Numeric(nocodb 形态);security_type = 逗号多值串(市场码+大类码扩展,
见 shared_kernel/nocodb_schema.SECURITY_TYPE_EXPAND)。
NocoDB 系统列(id/created_at/...)应用不写入。
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, declarative_base, mapped_column

# 创建基础类
Base = declarative_base()


class NocoDBColumns:
    """NocoDB 系统列 mixin(应用不写入;id 由 DB serial 默认值填充)."""

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class BaseKline(NocoDBColumns, Base):
    """K 线数据表基类(长 K:日/周/月/季/年).

    trade_time = Date(北京日期)。OHLCV 数值 = Numeric(nocodb 形态)。
    """

    __abstract__ = True

    # 组合主键(ORM 层):证券代码 + 交易日期(DB 层为 UNIQUE 约束 uq_*)
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    trade_time: Mapped[date] = mapped_column(Date, primary_key=True)

    # OHLCV 数据
    open: Mapped[Decimal] = mapped_column(Numeric)
    high: Mapped[Decimal] = mapped_column(Numeric)
    low: Mapped[Decimal] = mapped_column(Numeric)
    close: Mapped[Decimal] = mapped_column(Numeric)
    volume: Mapped[int] = mapped_column(BigInteger)
    amount: Mapped[Decimal | None] = mapped_column(Numeric)

    # 品种类型(逗号多值:市场码+大类码,写入端经 expand_security_type)
    security_type: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<Kline (symbol={self.symbol}, trade_time={self.trade_time}, close={self.close})>"


class BaseKlineMinute(NocoDBColumns, Base):
    """K 线数据表基类(分钟 K:1~120 分钟).

    trade_time = naive DateTime(北京 wall-clock,无 tz)。
    is_final: 实时订阅写 false(未闭合),次日 query_kline 覆盖写 true(定稿)。
    """

    __abstract__ = True

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    trade_time: Mapped[datetime] = mapped_column(DateTime, primary_key=True)

    open: Mapped[Decimal] = mapped_column(Numeric)
    high: Mapped[Decimal] = mapped_column(Numeric)
    low: Mapped[Decimal] = mapped_column(Numeric)
    close: Mapped[Decimal] = mapped_column(Numeric)
    volume: Mapped[int] = mapped_column(BigInteger)
    amount: Mapped[Decimal | None] = mapped_column(Numeric)
    security_type: Mapped[str | None] = mapped_column(Text)
    is_final: Mapped[bool] = mapped_column(Boolean, default=True)


# 为每个 Interval 创建单独的表
class KlineMin1(BaseKlineMinute):
    __tablename__ = "kline_min1"


class KlineMin3(BaseKlineMinute):
    __tablename__ = "kline_min3"


class KlineMin5(BaseKlineMinute):
    __tablename__ = "kline_min5"


class KlineMin10(BaseKlineMinute):
    __tablename__ = "kline_min10"


class KlineMin15(BaseKlineMinute):
    __tablename__ = "kline_min15"


class KlineMin30(BaseKlineMinute):
    __tablename__ = "kline_min30"


class KlineMin60(BaseKlineMinute):
    __tablename__ = "kline_min60"


class KlineMin120(BaseKlineMinute):
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
from galaxy_core.shared_kernel.enums.interval import Interval  # noqa: E402

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
