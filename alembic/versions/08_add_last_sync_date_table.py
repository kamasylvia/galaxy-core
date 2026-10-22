"""add_last_sync_date_table

Revision ID: 08_add_last_sync_date
Revises: 07_drop_completeness_log
Create Date: 2026-06-04 00:00:00.000000

创建 last_sync_date 表（Phase 2 增量同步基础设施）。
用于跟踪每个 (symbol, interval) 对的最后同步交易日期，
替代 v1.2 的完整性检查机制。

已有部署的回填 SQL（新部署由同步自动填充）：

INSERT INTO last_sync_date (symbol, interval, last_sync_date, updated_at)
SELECT symbol, 'day', MAX(trade_time)::date, NOW() FROM kline_day GROUP BY symbol
ON CONFLICT (symbol, interval) DO UPDATE SET last_sync_date = EXCLUDED.last_sync_date;

-- 对 min1, week, month, season, year 等周期重复上述语句。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '08_add_last_sync_date'
down_revision: Union[str, Sequence[str], None] = '07_drop_completeness_log'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 last_sync_date 表."""
    inspector = inspect(op.get_bind())

    if not inspector.has_table('last_sync_date'):
        op.create_table(
            'last_sync_date',
            sa.Column('symbol', sa.String(length=20), nullable=False, comment='证券代码'),
            sa.Column('interval', sa.String(length=20), nullable=False, comment='K 线周期'),
            sa.Column('last_sync_date', sa.Date(), nullable=False, comment='最后同步交易日期'),
            sa.Column(
                'updated_at',
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
                comment='记录更新时间',
            ),
            sa.PrimaryKeyConstraint('symbol', 'interval'),
        )

    indexes = {idx['name'] for idx in inspector.get_indexes('last_sync_date')}
    if 'idx_last_sync_date_interval' not in indexes:
        op.create_index(
            'idx_last_sync_date_interval',
            'last_sync_date',
            ['interval'],
            unique=False,
        )


def downgrade() -> None:
    """删除 last_sync_date 表."""
    inspector = inspect(op.get_bind())

    indexes = {idx['name'] for idx in inspector.get_indexes('last_sync_date')}
    if 'idx_last_sync_date_interval' in indexes:
        op.drop_index('idx_last_sync_date_interval', table_name='last_sync_date')

    if inspector.has_table('last_sync_date'):
        op.drop_table('last_sync_date')
