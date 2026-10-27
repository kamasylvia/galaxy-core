"""AUTO-GENERATED from nocodb schema(2026-08-26 回迁 P4).

生成器: scripts/nocodb_reimport/gen_models.py。表名=nocodb 中文表名;
业务列名=原 pg 列名;NocoDB 系统列应用不写。
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from .kline import Base


class LastSyncDate(Base):
    """表 "last_sync_date"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "last_sync_date"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="NocoDB 行 id(serial)")
    symbol: Mapped[str | None] = mapped_column(Text)
    interval: Mapped[str | None] = mapped_column(Text)
    last_sync_date: Mapped[date | None] = mapped_column(Date)
    data_type: Mapped[str | None] = mapped_column(Text)
    sync_type: Mapped[str | None] = mapped_column(Text)
    scope_key: Mapped[str | None] = mapped_column(Text)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"<LastSyncDate(id={self.id!r})>"
