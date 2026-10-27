"""AUTO-GENERATED from nocodb schema(2026-08-26 回迁 P4).

生成器: scripts/nocodb_reimport/gen_models.py。表名=nocodb 中文表名;
业务列名=原 pg 列名;NocoDB 系统列应用不写。
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from .kline import Base


class IndexConstituent(Base):
    """表 "index_constituent"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "index_constituent"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    index_code: Mapped[str] = mapped_column(Text, primary_key=True)
    con_code: Mapped[str] = mapped_column(Text, primary_key=True)
    in_date: Mapped[date] = mapped_column(Date, primary_key=True)
    out_date: Mapped[date | None] = mapped_column(Date)
    index_name: Mapped[str | None] = mapped_column(Text)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<IndexConstituent(index_code={self.index_code!r}"
            f", con_code={self.con_code!r}"
            f", in_date={self.in_date!r})>"
        )


class IndexWeight(Base):
    """表 "index_weight"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "index_weight"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    index_code: Mapped[str] = mapped_column(Text, primary_key=True)
    con_code: Mapped[str] = mapped_column(Text, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    total_share: Mapped[Decimal | None] = mapped_column(Numeric)
    free_share_ratio: Mapped[Decimal | None] = mapped_column(Numeric)
    calc_share: Mapped[Decimal | None] = mapped_column(Numeric)
    weight_factor: Mapped[Decimal | None] = mapped_column(Numeric)
    weight: Mapped[Decimal | None] = mapped_column(Numeric)
    close: Mapped[Decimal | None] = mapped_column(Numeric)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<IndexWeight(index_code={self.index_code!r}"
            f", con_code={self.con_code!r}"
            f", trade_date={self.trade_date!r})>"
        )


class IndustryBaseInfo(Base):
    """表 "industry_base_info"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "industry_base_info"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    index_code: Mapped[str] = mapped_column(Text, primary_key=True)
    industry_code: Mapped[str] = mapped_column(Text, primary_key=True)
    level_type: Mapped[int | None] = mapped_column(BigInteger)
    level1_name: Mapped[str | None] = mapped_column(Text)
    level2_name: Mapped[str | None] = mapped_column(Text)
    level3_name: Mapped[str | None] = mapped_column(Text)
    is_pub: Mapped[bool | None] = mapped_column(Boolean)
    change_reason: Mapped[str | None] = mapped_column(Text)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<IndustryBaseInfo(index_code={self.index_code!r}"
            f", industry_code={self.industry_code!r})>"
        )


class IndustryConstituent(Base):
    """表 "industry_constituent"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "industry_constituent"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    index_code: Mapped[str] = mapped_column(Text, primary_key=True)
    con_code: Mapped[str] = mapped_column(Text, primary_key=True)
    in_date: Mapped[date] = mapped_column(Date, primary_key=True)
    out_date: Mapped[date | None] = mapped_column(Date)
    index_name: Mapped[str | None] = mapped_column(Text)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<IndustryConstituent(index_code={self.index_code!r}"
            f", con_code={self.con_code!r}"
            f", in_date={self.in_date!r})>"
        )


class IndustryDaily(Base):
    """表 "industry_daily"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "industry_daily"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    index_code: Mapped[str] = mapped_column(Text, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal | None] = mapped_column(Numeric)
    high: Mapped[Decimal | None] = mapped_column(Numeric)
    low: Mapped[Decimal | None] = mapped_column(Numeric)
    close: Mapped[Decimal | None] = mapped_column(Numeric)
    pre_close: Mapped[Decimal | None] = mapped_column(Numeric)
    volume: Mapped[Decimal | None] = mapped_column(Numeric)
    amount: Mapped[Decimal | None] = mapped_column(Numeric)
    pb: Mapped[Decimal | None] = mapped_column(Numeric)
    pe: Mapped[Decimal | None] = mapped_column(Numeric)
    total_cap: Mapped[Decimal | None] = mapped_column(Numeric)
    a_float_cap: Mapped[Decimal | None] = mapped_column(Numeric)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"<IndustryDaily(index_code={self.index_code!r}, trade_date={self.trade_date!r})>"


class IndustryWeight(Base):
    """表 "industry_weight"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "industry_weight"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    index_code: Mapped[str] = mapped_column(Text, primary_key=True)
    con_code: Mapped[str] = mapped_column(Text, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    weight: Mapped[Decimal | None] = mapped_column(Numeric)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<IndustryWeight(index_code={self.index_code!r}"
            f", con_code={self.con_code!r}"
            f", trade_date={self.trade_date!r})>"
        )
