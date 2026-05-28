"""证券基础信息模型.

对应 AmazingData 开发手册 3.5.2.1 证券基础信息表.
"""

from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .kline import Base


class StockBasic(Base):
    """证券基础信息表.

    字段说明:
    - symbol: 证券代码，如 600000.SH (主键)
    - security_name: 证券简称
    - comp_name: 公司全称
    - pinyin: 拼音简称
    - list_date: 上市日期
    - delist_date: 退市日期
    - security_type: 品种类型
    """

    __tablename__ = "stock_basic"

    symbol: Mapped[str] = mapped_column(
        String(20), primary_key=True, comment="证券代码"
    )
    security_name: Mapped[Optional[str]] = mapped_column(
        String(100), comment="证券简称"
    )
    comp_name: Mapped[Optional[str]] = mapped_column(
        String(200), comment="公司全称"
    )
    pinyin: Mapped[Optional[str]] = mapped_column(
        String(50), comment="拼音简称"
    )
    list_date: Mapped[Optional[date]] = mapped_column(
        Date, comment="上市日期"
    )
    delist_date: Mapped[Optional[date]] = mapped_column(
        Date, comment="退市日期"
    )
    security_type: Mapped[Optional[str]] = mapped_column(
        String(20), comment="品种类型"
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

    def __repr__(self) -> str:
        return f"<StockBasic(symbol={self.symbol}, name={self.security_name}, list={self.list_date})>"
