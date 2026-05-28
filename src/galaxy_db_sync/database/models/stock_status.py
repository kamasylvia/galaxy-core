"""历史证券状态模型.

对应 AmazingData 开发手册 3.5.2.10 历史证券信息.
包含停牌、ST、涨跌停价、除权除息等日频状态.
"""

from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from .kline import Base


class StockStatus(Base):
    """历史证券状态表.

    字段说明:
    - symbol: 证券代码 (组合主键之一)
    - trade_date: 交易日期 (组合主键之一)
    - preclose: 前收盘价
    - high_limited: 涨停价
    - low_limited: 跌停价
    - is_st: 是否为 ST 股票
    - is_susp: 是否停牌
    - is_xr: 是否除权
    - is_wd: 是否除息
    """

    __tablename__ = "stock_status"

    symbol: Mapped[str] = mapped_column(
        String(20), primary_key=True, comment="证券代码"
    )
    trade_date: Mapped[date] = mapped_column(
        Date, primary_key=True, comment="交易日期"
    )
    preclose: Mapped[Optional[float]] = mapped_column(
        Float, comment="前收盘价"
    )
    high_limited: Mapped[Optional[float]] = mapped_column(
        Float, comment="涨停价"
    )
    low_limited: Mapped[Optional[float]] = mapped_column(
        Float, comment="跌停价"
    )
    is_st: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否ST"
    )
    is_susp: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否停牌"
    )
    is_xr: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否除权"
    )
    is_wd: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否除息"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, comment="创建时间"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

    # 主键 (symbol, trade_date) 已自动创建唯一索引
    # 额外索引: 按日期查询所有股票状态（如"某日哪些股票停牌"）
    __table_args__ = (
        Index("idx_stock_status_date", "trade_date"),
    )

    def __repr__(self) -> str:
        return f"<StockStatus(symbol={self.symbol}, date={self.trade_date}, st={self.is_st}, susp={self.is_susp})>"
