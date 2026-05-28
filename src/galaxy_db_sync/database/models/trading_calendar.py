"""交易日历数据模型."""

from sqlalchemy import Column, Integer, Date, Boolean, DateTime
from sqlalchemy.sql import func

from galaxy_db_sync.database.models.kline import Base


class TradingCalendar(Base):
    """交易日历表模型."""

    __tablename__ = "trading_calendar"

    trade_date = Column(Date, primary_key=True)  # 交易日期
    is_trading_day = Column(Boolean, default=True)  # 是否为交易日
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<TradingCalendar(trade_date='{self.trade_date}', is_trading_day={self.is_trading_day})>"
