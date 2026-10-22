"""AUTO-GENERATED from nocodb schema(2026-08-26 回迁 P4).

生成器: scripts/nocodb_reimport/gen_models.py。表名=nocodb 中文表名;
业务列名=原 pg 列名;NocoDB 系统列应用不写。
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Float, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from .kline import Base


class LongHuBang(Base):
    """表 "long_hu_bang"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "long_hu_bang"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    market_code: Mapped[str] = mapped_column(Text, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    trader_name: Mapped[str] = mapped_column(Text, primary_key=True)
    flow_mark: Mapped[str] = mapped_column(Text, primary_key=True)
    security_name: Mapped[str | None] = mapped_column(Text)
    reason_type: Mapped[str | None] = mapped_column(Text)
    reason_type_name: Mapped[str | None] = mapped_column(Text)
    # 2026-08-27 对齐 qnap nocodb:change_range 由 numeric 改为 double precision
    change_range: Mapped[float | None] = mapped_column(Float)
    buy_amount: Mapped[Decimal | None] = mapped_column(Numeric)
    sell_amount: Mapped[Decimal | None] = mapped_column(Numeric)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric)
    total_volume: Mapped[Decimal | None] = mapped_column(Numeric)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<LongHuBang(market_code={self.market_code!r}"
            f", trade_date={self.trade_date!r}"
            f", trader_name={self.trader_name!r}"
            f", flow_mark={self.flow_mark!r})>"
        )


class BlockTrading(Base):
    """表 "block_trading"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "block_trading"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    market_code: Mapped[str] = mapped_column(Text, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    b_buyer_name: Mapped[str] = mapped_column(Text, primary_key=True)
    b_seller_name: Mapped[str] = mapped_column(Text, primary_key=True)
    b_share_price: Mapped[Decimal | None] = mapped_column(Numeric)
    b_share_volume: Mapped[Decimal | None] = mapped_column(Numeric)
    b_frequency: Mapped[int | None] = mapped_column(BigInteger)
    block_avg_volume: Mapped[Decimal | None] = mapped_column(Numeric)
    b_share_amount: Mapped[Decimal | None] = mapped_column(Numeric)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<BlockTrading(market_code={self.market_code!r}"
            f", trade_date={self.trade_date!r}"
            f", b_buyer_name={self.b_buyer_name!r}"
            f", b_seller_name={self.b_seller_name!r})>"
        )


class MarginDetailDaily(Base):
    """表 "margin_detail_daily"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "margin_detail_daily"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    market_code: Mapped[str] = mapped_column(Text, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    security_name: Mapped[str | None] = mapped_column(Text)
    borrow_money_balance: Mapped[Decimal | None] = mapped_column(Numeric)
    purch_with_borrow_money: Mapped[Decimal | None] = mapped_column(Numeric)
    repayment_of_borrow_money: Mapped[Decimal | None] = mapped_column(Numeric)
    sec_lending_balance: Mapped[Decimal | None] = mapped_column(Numeric)
    sales_of_borrowed_sec: Mapped[Decimal | None] = mapped_column(Numeric)
    repayment_of_borrow_sec: Mapped[Decimal | None] = mapped_column(Numeric)
    sec_lending_balance_vol: Mapped[Decimal | None] = mapped_column(Numeric)
    margin_trade_balance: Mapped[Decimal | None] = mapped_column(Numeric)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<MarginDetailDaily(market_code={self.market_code!r}, trade_date={self.trade_date!r})>"
        )


class MarginSummaryDaily(Base):
    """表 "margin_summary_daily"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "margin_summary_daily"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    sum_borrow_money_balance: Mapped[Decimal | None] = mapped_column(Numeric)
    sum_purch_with_borrow_money: Mapped[Decimal | None] = mapped_column(Numeric)
    sum_repayment_of_borrow_money: Mapped[Decimal | None] = mapped_column(Numeric)
    sum_sec_lending_balance: Mapped[Decimal | None] = mapped_column(Numeric)
    sum_sales_of_borrowed_sec: Mapped[Decimal | None] = mapped_column(Numeric)
    sum_margin_trade_balance: Mapped[Decimal | None] = mapped_column(Numeric)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"<MarginSummaryDaily(trade_date={self.trade_date!r})>"
