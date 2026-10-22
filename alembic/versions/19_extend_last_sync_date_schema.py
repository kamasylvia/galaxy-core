"""extend last_sync_date schema for phase 1&2 incremental sync

Revision ID: 19_extend_last_sync_date_schema
Revises: 18_drop_unused_phase02_tables
Create Date: 2026-06-19 00:00:00.000000

Phase 03(2026-06-19, 见 .planning/phases/03-incremental-sync-alignment/03-CONTEXT.md D-03/D-19/D-20).

为 last_sync_date 表加第三种维度模式 (sync_type, scope_key),使 Phase 1&2 表
(index_weight / industry_weight / amazingdata 4 表 / akshare sector)能走
统一的 last_sync_date 增量机制,与现有 K线(symbol, interval)/ 财务(symbol, data_type)
两种模式并列。

三模式 CHECK(放宽,兼容现有 48455 行 K线/财务数据):
- 模式 1 (K线): interval NOT NULL, data_type NULL, sync_type NULL
- 模式 2 (财务): interval NULL, data_type NOT NULL, sync_type NULL
- 模式 3 (Phase 1&2): interval NULL, data_type NULL, sync_type NOT NULL

schema drift 修正:生产 DB 缺 ck_last_sync_date_interval_or_data_type
(model 定义了但 DB 没有),本 migration 补齐(三模式版本)。

注(2026-06-19 修订):原 Phase 03 计划编号 18,但被 Phase 02 范围修订
(drop unused phase 02 tables)占用。重编号 19,down_revision=18。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = '19_extend_last_sync_date_schema'
down_revision: Union[str, Sequence[str], None] = '18_drop_unused_phase02_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 三模式 CHECK 定义
_THREE_MODE_CHECK = (
    "(interval IS NOT NULL AND data_type IS NULL AND sync_type IS NULL) OR "
    "(interval IS NULL AND data_type IS NOT NULL AND sync_type IS NULL) OR "
    "(interval IS NULL AND data_type IS NULL AND sync_type IS NOT NULL)"
)
_CHECK_NAME = "ck_last_sync_date_interval_or_data_type"
_UQ_NAME = "uq_last_sync_date_sync_type_scope_key"


def upgrade() -> None:
    """ADD 2 列 + 补/改 CHECK 三模式 + 新 UNIQUE(sync_type, scope_key)."""
    bind = op.get_bind()
    inspector = inspect(bind)

    # 1. ADD 2 列(幂等)
    existing_cols = {c["name"] for c in inspector.get_columns("last_sync_date")}
    if "sync_type" not in existing_cols:
        op.add_column(
            "last_sync_date",
            sa.Column(
                "sync_type",
                sa.String(length=50),
                nullable=True,
                comment="数据类标识(index_weight/long_hu_bang/akshare_sector_fund_flow/...); "
                        "Phase 1&2 表增量模式,K线/财务行为 NULL",
            ),
        )
    if "scope_key" not in existing_cols:
        op.add_column(
            "last_sync_date",
            sa.Column(
                "scope_key",
                sa.String(length=50),
                nullable=True,
                comment="natural key(index_code/market_code/channel); "
                        "全市场汇总表(margin_summary)为 NULL",
            ),
        )

    # 2. CHECK:schema drift 修正。生产 DB 缺,model 已定义。
    #    DROP 旧 CHECK(若存在,二模式版本)再 ADD 新 CHECK(三模式)。
    existing_checks = {
        c["name"] for c in inspector.get_check_constraints("last_sync_date")
    }
    if _CHECK_NAME in existing_checks:
        op.drop_constraint(_CHECK_NAME, "last_sync_date", type_="check")
    op.create_check_constraint(_CHECK_NAME, "last_sync_date", _THREE_MODE_CHECK)

    # 3. 新 UNIQUE(sync_type, scope_key)
    #    PostgreSQL 标准 UNIQUE 允许多个 (sync_type, NULL) 共存(NULL 不参与),
    #    margin_summary(scope_key=NULL) 每日 UPSERT 单行无问题。
    existing_uqs = {
        c["name"] for c in inspector.get_unique_constraints("last_sync_date")
    }
    if _UQ_NAME not in existing_uqs:
        op.create_unique_constraint(
            _UQ_NAME, "last_sync_date", ["sync_type", "scope_key"]
        )


def downgrade() -> None:
    """DROP 新 UNIQUE + CHECK(回退为旧二模式)+ DROP 2 列."""
    bind = op.get_bind()
    inspector = inspect(bind)

    existing_uqs = {
        c["name"] for c in inspector.get_unique_constraints("last_sync_date")
    }
    if _UQ_NAME in existing_uqs:
        op.drop_constraint(_UQ_NAME, "last_sync_date", type_="unique")

    existing_checks = {
        c["name"] for c in inspector.get_check_constraints("last_sync_date")
    }
    if _CHECK_NAME in existing_checks:
        op.drop_constraint(_CHECK_NAME, "last_sync_date", type_="check")
        # 回退为旧二模式 CHECK(model 03-02 前的定义)
        op.create_check_constraint(
            _CHECK_NAME,
            "last_sync_date",
            "(interval IS NOT NULL AND data_type IS NULL) OR "
            "(interval IS NULL AND data_type IS NOT NULL)",
        )

    existing_cols = {c["name"] for c in inspector.get_columns("last_sync_date")}
    if "scope_key" in existing_cols:
        op.drop_column("last_sync_date", "scope_key")
    if "sync_type" in existing_cols:
        op.drop_column("last_sync_date", "sync_type")
