"""AUTO-GENERATED from nocodb schema(2026-08-26 回迁 P4).

生成器: scripts/nocodb_reimport/gen_models.py。表名=nocodb 中文表名;
业务列名=原 pg 列名;NocoDB 系统列应用不写。
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from .kline import Base


class AkshareSectorFundFlowDaily(Base):
    """表 "akshare_sector_fund_flow_daily"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "akshare_sector_fund_flow_daily"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    sector_type: Mapped[str] = mapped_column(Text, primary_key=True)
    sector_name: Mapped[str] = mapped_column(Text, primary_key=True)
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric)
    main_net_amount: Mapped[Decimal | None] = mapped_column(Numeric)
    main_net_pct: Mapped[Decimal | None] = mapped_column(Numeric)
    super_large_net_amount: Mapped[Decimal | None] = mapped_column(Numeric)
    super_large_net_pct: Mapped[Decimal | None] = mapped_column(Numeric)
    large_net_amount: Mapped[Decimal | None] = mapped_column(Numeric)
    large_net_pct: Mapped[Decimal | None] = mapped_column(Numeric)
    medium_net_amount: Mapped[Decimal | None] = mapped_column(Numeric)
    medium_net_pct: Mapped[Decimal | None] = mapped_column(Numeric)
    small_net_amount: Mapped[Decimal | None] = mapped_column(Numeric)
    small_net_pct: Mapped[Decimal | None] = mapped_column(Numeric)
    top_stock: Mapped[str | None] = mapped_column(Text)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<AkshareSectorFundFlowDaily(trade_date={self.trade_date!r}"
            f", sector_type={self.sector_type!r}"
            f", sector_name={self.sector_name!r})>"
        )
