"""AUTO-GENERATED from nocodb schema(2026-08-26 回迁 P4).

生成器: scripts/nocodb_reimport/gen_models.py。表名=nocodb 中文表名;
业务列名=原 pg 列名;NocoDB 系统列应用不写。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from .kline import Base


class SyncState(Base):
    """表 "sync_state"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="NocoDB 行 id(serial)")
    sync_type: Mapped[str | None] = mapped_column(Text)
    period_identifier: Mapped[str | None] = mapped_column(Text)
    sync_status: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    records_synced: Mapped[int | None] = mapped_column(BigInteger)
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int | None] = mapped_column(BigInteger)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"<SyncState(id={self.id!r})>"
