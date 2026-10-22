"""drop_completeness_check_log

Revision ID: 07_drop_completeness_log
Revises: 47922c8e5478
Create Date: 2026-06-04 00:00:00.000000

删除 completeness_check_log 表（Phase 1 废弃代码清理）。
该表及相关代码已在 v1.3 中移除，由 last_sync_date 机制替代审计。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '07_drop_completeness_log'
down_revision: Union[str, Sequence[str], None] = '47922c8e5478'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删除 completeness_check_log 表.

    用 ``DROP TABLE IF EXISTS`` 而非 ``try/except: pass`` 包 ``op.drop_table`` ——
    后者在 alembic transactional DDL 下会让 PG 事务进入 aborted 状态,吞异常不
    rollback,导致后续 SQL 全部 InFailedSqlTransaction,整个 migration 回滚。
    """
    op.execute('DROP TABLE IF EXISTS completeness_check_log')


def downgrade() -> None:
    """重建 completeness_check_log 表."""
    op.create_table(
        'completeness_check_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('check_type', sa.String(length=30), nullable=False),
        sa.Column('check_date', sa.String(length=10), nullable=False),
        sa.Column('check_intervals', sa.JSON(), nullable=False),
        sa.Column('symbols_checked', sa.Integer(), nullable=True),
        sa.Column('total_missing', sa.Integer(), nullable=True),
        sa.Column('repair_triggered', sa.String(length=10), nullable=True),
        sa.Column('repair_result', sa.Text(), nullable=True),
        sa.Column('check_duration_ms', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_completeness_check_date', 'completeness_check_log', ['check_date'], unique=False)
    op.create_index('idx_completeness_check_type_date', 'completeness_check_log', ['check_type', 'check_date'], unique=False)
