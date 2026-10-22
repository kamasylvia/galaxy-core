"""drop_dead_code_tables

Revision ID: 05_drop_dead_code
Revises: cc36b7ffea14
Create Date: 2026-06-02 00:00:00.000000

删除 dead code 表:
- completeness_check_results: 未在生产代码中使用
- missing_data_confirmations: 未在生产代码中使用
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05_drop_dead_code'
down_revision: Union[str, Sequence[str], None] = 'cc36b7ffea14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删除 dead code 表.

    用 ``DROP TABLE IF EXISTS`` 而非 ``try/except: pass`` 包 ``op.drop_table`` ——
    后者在 alembic transactional DDL 下会让 PG 事务进入 aborted 状态,吞异常不
    rollback,导致后续 SQL 全部 InFailedSqlTransaction,整个 migration 回滚。
    """

    op.execute('DROP TABLE IF EXISTS completeness_check_results')
    op.execute('DROP TABLE IF EXISTS missing_data_confirmations')


def downgrade() -> None:
    """重建表（不推荐回退）."""

    op.create_table(
        'completeness_check_results',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(20), nullable=False, index=True, comment='证券代码'),
        sa.Column('interval', sa.String(20), nullable=False, index=True, comment='K线周期'),
        sa.Column('check_start', sa.Date(), nullable=False, index=True, comment='检查开始日期'),
        sa.Column('check_end', sa.Date(), nullable=False, index=True, comment='检查结束日期'),
        sa.Column('missing_start', sa.Date(), nullable=False, comment='缺失区间开始'),
        sa.Column('missing_end', sa.Date(), nullable=False, comment='缺失区间结束'),
        sa.Column('is_confirmed_missing', sa.Boolean(), default=False, comment='是否已确认缺失'),
        sa.Column('confirmation_reason', sa.String(50), nullable=True, comment='确认原因'),
        sa.Column('api_empty_checked_at', sa.DateTime(), nullable=True, comment='API检查时间'),
        sa.Column('discovered_at', sa.DateTime(), server_default=sa.func.now(), comment='发现时间'),
        sa.Column('last_checked_at', sa.DateTime(), server_default=sa.func.now(), comment='最后检查时间'),
        sa.Column('notes', sa.Text(), nullable=True, comment='备注'),
        sa.Column('status', sa.String(20), default='pending', index=True, comment='状态'),
        sa.Column('retry_count', sa.Integer(), default=0, comment='重试次数'),
        sa.Column('last_retry_at', sa.DateTime(), nullable=True, comment='最后重试时间'),
    )

    op.create_table(
        'missing_data_confirmations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(20), nullable=False, index=True, comment='证券代码'),
        sa.Column('interval', sa.String(20), nullable=False, index=True, comment='K线周期'),
        sa.Column('missing_start', sa.Date(), nullable=False, comment='缺失开始日期'),
        sa.Column('missing_end', sa.Date(), nullable=False, comment='缺失结束日期'),
        sa.Column('confirmation_type', sa.String(50), nullable=False, comment='确认类型'),
        sa.Column('api_response', sa.Text(), nullable=True, comment='API响应详情'),
        sa.Column('confirmed_at', sa.DateTime(), server_default=sa.func.now(), comment='确认时间'),
        sa.Column('trading_days_in_range', sa.Integer(), nullable=True, comment='范围内交易日数'),
    )
