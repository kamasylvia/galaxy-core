"""交易日历数据模型."""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Boolean,
    DateTime,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from galaxy_db_bridge.database.core.connection import Base


class TradingCalendar(Base):
    """交易日历表模型."""

    __tablename__ = "trading_calendar"

    id = Column(Integer, primary_key=True, index=True)
    market = Column(
        String(50), nullable=False
    )  # 上海证券交易所(SH)/深圳证券交易所(SZ)/北京证券交易所(BJ) 等
    trade_date = Column(Date, nullable=False)  # 交易日期
    is_trading_day = Column(Boolean, default=True)  # 是否为交易日
    year = Column(Integer, nullable=False)  # 年份，用于年更策略
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # 添加唯一性约束：确保同一市场内同一天只有一条记录
    __table_args__ = (
        UniqueConstraint("market", "trade_date", name="uq_market_trade_date"),
    )

    def __repr__(self):
        return f"<TradingCalendar(id={self.id}, market='{self.market}', trade_date='{self.trade_date}', is_trading_day={self.is_trading_day})>"
