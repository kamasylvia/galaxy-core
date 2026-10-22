"""audit columns to timestamptz

Revision ID: 24_audit_timestamptz
Revises: 23_biz_timestamptz
Create Date: 2026-07-17 00:00:00.000000

补齐 migration 23 遗漏的审计列 / 运行时间列(均普通表,非 hypertable,ALTER TYPE 安全):

- last_sync_date.updated_at(ORM 已声明 timezone=True,DB 漂移,本 migration 对齐)
- sync_state 4 列:started_at/completed_at/created_at/updated_at(运行时间戳)
- financial 6 表 × 2 审计列:balance_sheet/cash_flow/income/profit_express/
  profit_notice/dividend 的 created_at/updated_at

这些表都是普通表(非 TimescaleDB hypertable),ALTER COLUMN TYPE 无 chunk 约束障碍,
直接 ALTER 即可。审计列语义是 UTC instant,USING ... AT TIME ZONE 'UTC'。

共 7 表 17 列。
"""
from typing import Sequence, Union

from alembic import op


revision: str = "24_audit_timestamptz"
down_revision: Union[str, Sequence[str], None] = "23_biz_timestamptz"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 普通表(非 hypertable)的审计列升级。直接 ALTER COLUMN TYPE。
# (table, columns) — columns 是需升级的列名列表
AUDIT_TABLES: list[tuple[str, list[str]]] = [
    ("last_sync_date", ["updated_at"]),
    ("sync_state", ["started_at", "completed_at", "created_at", "updated_at"]),
    ("balance_sheet", ["created_at", "updated_at"]),
    ("cash_flow", ["created_at", "updated_at"]),
    ("income", ["created_at", "updated_at"]),
    ("profit_express", ["created_at", "updated_at"]),
    ("profit_notice", ["created_at", "updated_at"]),
    ("dividend", ["created_at", "updated_at"]),
]


def upgrade() -> None:
    """审计列/运行时间列 → timestamptz(按 UTC 解释存量)."""
    for table, columns in AUDIT_TABLES:
        for col in columns:
            # updated_at/completed_at 可能为 NULL,fallback 到同表的 created_at/started_at
            # (前提是该列也在本表 columns 列表中)。否则用本列原值。
            fallback_col = None
            if col == "updated_at" and "created_at" in columns:
                fallback_col = "created_at"
            elif col == "completed_at" and "started_at" in columns:
                fallback_col = "started_at"

            if fallback_col:
                using = f"COALESCE({col}, {fallback_col})"
            else:
                using = col
            op.execute(
                f"ALTER TABLE {table} ALTER COLUMN {col} "
                f"TYPE timestamptz USING {using} AT TIME ZONE 'UTC';"
            )


def downgrade() -> None:
    """不可逆(timestamptz → naive 丢时区语义)."""
    pass
