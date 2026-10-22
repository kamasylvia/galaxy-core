"""fix last_sync_date unique constraint for NULL scope_key

Revision ID: 21_fix_lsd_unique
Revises: 20_symbol_nullable
Create Date: 2026-06-20 00:00:00.000000

修复 Phase 03(03-02)的 UNIQUE(sync_type, scope_key) 缺陷:
PostgreSQL 普通 UNIQUE 对 NULL 值不生效(NULL ≠ NULL),导致
scope_key=NULL 的全局表(margin_summary / index_weight / industry_weight)
可重复插入多条记录。

实测:industry_weight 产生 2 条 scope_key=NULL 行(6/17 + 6/18),
margin_summary 也会累积。get_last_sync_date 取 .first() 返回不确定行。

修复方案(D-24,见 03-CONTEXT):
1. DROP 原 UNIQUE constraint uq_last_sync_date_sync_type_scope_key
2. CREATE partial unique index:
   - scope_key IS NULL 时:仅 sync_type 唯一(全局表)
   - scope_key IS NOT NULL 时:(sync_type, scope_key) 组合唯一(per-symbol 表)
3. 清理现有重复行(保留 MAX(updated_at),即最新)

downgrade 无法精确恢复重复行(已清理),仅恢复 constraint 结构。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '21_fix_lsd_unique'
down_revision: Union[str, Sequence[str], None] = '20_symbol_nullable'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD_UQ = "uq_last_sync_date_sync_type_scope_key"
# partial index:全局表(scope_key IS NULL)按 sync_type 唯一
_UQ_GLOBAL = "uq_last_sync_date_sync_type_global"
# partial index:per-symbol 表(scope_key IS NOT NULL)按 (sync_type, scope_key) 唯一
_UQ_SCOPED = "uq_last_sync_date_sync_type_scoped"


def upgrade() -> None:
    """清理重复行 + DROP 旧 UNIQUE + CREATE 2 partial unique index."""
    bind = op.get_bind()

    # 1. 清理重复行:保留每组 (sync_type, scope_key) 的 MAX(updated_at) 行
    bind.execute(sa.text("""
        DELETE FROM last_sync_date
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY sync_type, scope_key
                           ORDER BY updated_at DESC, id DESC
                       ) AS rn
                FROM last_sync_date
                WHERE sync_type IS NOT NULL
            ) ranked
            WHERE rn > 1
        )
    """))

    # 2. DROP 旧 UNIQUE constraint(对 NULL 不生效)
    op.drop_constraint(_OLD_UQ, "last_sync_date", type_="unique")

    # 3. CREATE partial unique index
    #    全局表:scope_key IS NULL → sync_type 唯一
    op.create_index(
        _UQ_GLOBAL,
        "last_sync_date",
        ["sync_type"],
        unique=True,
        postgresql_where="scope_key IS NULL",
    )
    #    per-symbol 表:scope_key IS NOT NULL → (sync_type, scope_key) 唯一
    op.create_index(
        _UQ_SCOPED,
        "last_sync_date",
        ["sync_type", "scope_key"],
        unique=True,
        postgresql_where="scope_key IS NOT NULL",
    )


def downgrade() -> None:
    """DROP 2 partial index + 恢复旧 UNIQUE constraint(不恢复已清理的重复行)."""
    op.drop_index(_UQ_SCOPED, table_name="last_sync_date")
    op.drop_index(_UQ_GLOBAL, table_name="last_sync_date")
    op.create_unique_constraint(
        _OLD_UQ, "last_sync_date", ["sync_type", "scope_key"]
    )
