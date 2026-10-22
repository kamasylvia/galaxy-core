"""AUTO-GENERATED from nocodb schema(2026-08-26 回迁 P4).

生成器: scripts/nocodb_reimport/gen_models.py。表名=nocodb 中文表名;
业务列名=原 pg 列名;NocoDB 系统列应用不写。
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .kline import Base


class TradingCalendar(Base):
    """表 "trading_calendar"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "trading_calendar"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    is_trading_day: Mapped[bool | None] = mapped_column(Boolean)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"<TradingCalendar(trade_date={self.trade_date!r})>"
