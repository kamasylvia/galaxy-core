"""drop_empty_query_results

Revision ID: 06_drop_empty_query
Revises: 05_drop_dead_code
Create Date: 2026-06-02 00:00:01.000000

删除 empty_query_results 旧表（之前迁移未正确执行）。
该表已被 empty_data_cache 取代。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '06_drop_empty_query'
down_revision: Union[str, Sequence[str], None] = '05_drop_dead_code'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删除 empty_query_results 旧表.

    用 ``DROP TABLE IF EXISTS`` 而非 ``try/except: pass`` 包 ``op.drop_table`` ——
    后者在 alembic transactional DDL 下会让 PG 事务进入 aborted 状态,吞异常不
    rollback,导致后续 SQL 全部 InFailedSqlTransaction,整个 migration 回滚。
    """
    op.execute('DROP TABLE IF EXISTS empty_query_results')


def downgrade() -> None:
    """重建 empty_query_results 表."""
    op.create_table(
        'empty_query_results',
        sa.Column('symbol', sa.String(length=20), primary_key=True, comment='证券代码'),
        sa.Column('interval', sa.String(length=20), primary_key=True, comment='K线周期'),
        sa.Column('start_date', sa.Date(), primary_key=True, comment='查询开始日期'),
        sa.Column('end_date', sa.Date(), primary_key=True, comment='查询结束日期'),
    )
