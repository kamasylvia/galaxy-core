"""龙虎榜.change_range 对齐 qnap nocodb:numeric → double precision(2026-08-27).

NocoDB Finance/Galaxy source 侧把 龙虎榜.change_range 列类型从 numeric
改为 double precision(nocodb Decimal 列调整)。全库 36 表 diff 仅此一处。
数据无需回填(本地 1,413,562 行 > qnap 1,413,443 行,本地领先)。

Revision ID: 27_lhb_change_range_float8
Revises: 26_business_pk_defaults
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "27_lhb_change_range_float8"
down_revision: str | Sequence[str] | None = "26_business_pk_defaults"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _current_type(tbl: str, col: str) -> str | None:
    conn = op.get_bind()
    row = conn.execute(
        text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
        ),
        {"t": tbl, "c": col},
    ).first()
    return row[0] if row else None


def upgrade() -> None:
    if _current_type("龙虎榜", "change_range") == "numeric":
        op.execute('ALTER TABLE public."龙虎榜" ALTER COLUMN change_range TYPE double precision')


def downgrade() -> None:
    if _current_type("龙虎榜", "change_range") == "double precision":
        op.execute('ALTER TABLE public."龙虎榜" ALTER COLUMN change_range TYPE numeric')
