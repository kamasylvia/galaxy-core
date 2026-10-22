"""alter last_sync_date.symbol to nullable

Revision ID: 20_symbol_nullable
Revises: 19_extend_last_sync_date_schema
Create Date: 2026-06-19 00:00:00.000000

修复 migration 19 遗漏:last_sync_date.symbol 列应为 nullable 以支持
Phase 1&2 表第三模式(sync_type, scope_key, symbol=NULL)。

migration 19 加了三模式 CHECK + sync_type/scope_key 列,但漏改 symbol NOT NULL。
导致 Phase 03 margin_summary(scope_key=None, symbol=NULL)写入失败:
NotNullViolationError: null value in column "symbol"。

本 migration 补 ALTER COLUMN symbol DROP NOT NULL。
ORM model 已是 nullable(03-02 改过),此 migration 对齐 DB schema。

注:revision ID 限 ≤32 字符(alembic_version.version varchar(32))。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20_symbol_nullable'
down_revision: Union[str, Sequence[str], None] = '19_extend_last_sync_date_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """ALTER symbol DROP NOT NULL(支持 Phase 1&2 第三模式 symbol=NULL)."""
    op.alter_column(
        "last_sync_date",
        "symbol",
        existing_type=sa.String(length=20),
        nullable=True,
    )


def downgrade() -> None:
    """回退:symbol 改回 NOT NULL(但已有 sync_type 模式行会冲突,仅 schema 回退)."""
    op.alter_column(
        "last_sync_date",
        "symbol",
        existing_type=sa.String(length=20),
        nullable=False,
    )
