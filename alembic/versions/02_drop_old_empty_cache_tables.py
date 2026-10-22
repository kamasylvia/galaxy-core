"""drop_old_empty_cache_tables

Revision ID: 02_drop_old_tables
Revises: 02_empty_data_cache_and_mv
Create Date: 2026-06-01 00:00:00.000000

D-2.2-3: 直接删除旧表 empty_query_caches 和 empty_query_results，
不迁移数据。旧缓存在后续同步中自动重新生成。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '02_drop_old_tables'
down_revision: Union[str, Sequence[str], None] = '02_empty_data_cache_and_mv'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删除旧表 empty_query_caches 和 empty_query_results (per D-2.2-3).

    注意:不能用 ``try/except: pass`` 包 ``op.drop_table`` —— alembic 在
    transactional DDL 模式下,一次 drop 失败会让 PG 事务进入 aborted 状态,
    ``except: pass`` 吞掉异常但不 rollback,后续所有 SQL(含 alembic 自己的
    UPDATE alembic_version)都报 InFailedSqlTransaction,整个 migration 回滚。
    用 ``DROP TABLE IF EXISTS`` 让 PG 原生处理"表不存在",事务始终保持正常。
    """

    op.execute('DROP TABLE IF EXISTS empty_query_caches')
    op.execute('DROP TABLE IF EXISTS empty_query_results')


def downgrade() -> None:
    """重建旧表 empty_query_caches 和 empty_query_results."""

    op.create_table(
        'empty_query_caches',
        sa.Column('symbol', sa.String(length=20), primary_key=True, comment='证券代码'),
        sa.Column('interval', sa.String(length=20), primary_key=True, comment='K 线周期'),
        sa.Column('start_date', sa.Date(), primary_key=True, comment='查询开始日期'),
        sa.Column('end_date', sa.Date(), primary_key=True, comment='查询结束日期'),
    )

    op.create_table(
        'empty_query_results',
        sa.Column('symbol', sa.String(length=20), primary_key=True, comment='证券代码'),
        sa.Column('interval', sa.String(length=20), primary_key=True, comment='K 线周期'),
        sa.Column('start_date', sa.Date(), primary_key=True, comment='查询开始日期'),
        sa.Column('end_date', sa.Date(), primary_key=True, comment='查询结束日期'),
    )
