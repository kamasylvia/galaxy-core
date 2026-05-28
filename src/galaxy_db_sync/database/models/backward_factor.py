"""后复权因子模型.

对应 AmazingData API get_backward_factor.
日频后复权因子，用于将历史价格调整为后复权价格.
"""

from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from .kline import Base


class BackwardFactor(Base):
    """后复权因子表.

    字段说明:
    - symbol: 证券代码 (组合主键之一)
    - trade_date: 交易日期 (组合主键之一)
    - factor: 后复权因子值
    """

    __tablename__ = "backward_factor"

    symbol: Mapped[str] = mapped_column(
        String(20), primary_key=True, comment="证券代码"
    )
    trade_date: Mapped[date] = mapped_column(
        Date, primary_key=True, comment="交易日期"
    )
    factor: Mapped[float] = mapped_column(
        Float, nullable=False, comment="后复权因子"
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
    # 额外索引: 按日期查询所有股票因子
    __table_args__ = (
        Index("idx_backward_factor_date", "trade_date"),
    )

    def __repr__(self) -> str:
        return f"<BackwardFactor(symbol={self.symbol}, date={self.trade_date}, factor={self.factor})>"
