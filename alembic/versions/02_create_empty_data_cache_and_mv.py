"""create_empty_data_cache_and_mv

Revision ID: 02_empty_data_cache_and_mv
Revises: 45e4b4826455
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '02_empty_data_cache_and_mv'
down_revision: Union[str, Sequence[str], None] = '45e4b4826455'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 empty_data_cache 表 + Materialized View + CompletenessCheckResult 扩展列."""

    # 1. 创建 empty_data_cache 表（合并 EmptyQueryCache + EmptyQueryResult）
    op.create_table(
        'empty_data_cache',
        sa.Column('symbol', sa.String(length=20), nullable=False, comment='证券代码'),
        sa.Column('interval', sa.String(length=20), nullable=False, comment='K 线周期'),
        sa.Column('trade_date', sa.Date(), nullable=False, comment='交易日期'),
        sa.Column(
            'reason', sa.String(length=20), nullable=False,
            comment='空数据原因: delisted / suspended / api_empty',
        ),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.PrimaryKeyConstraint('symbol', 'interval', 'trade_date'),
    )
    op.create_index(
        'idx_empty_data_cache_date', 'empty_data_cache', ['trade_date'], unique=False
    )

    # 2. 创建 Materialized View（汇总每个 symbol 每个 interval 的完整性摘要）
    op.execute(text("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_symbol_completeness AS
        SELECT
            k.symbol,
            k.interval,
            MAX(k.trade_time::date) AS last_complete_date,
            COUNT(*) AS total_records,
            NOW() AS refreshed_at
        FROM (
            SELECT symbol, 'day' AS interval, trade_time FROM kline_day
            UNION ALL
            SELECT symbol, 'week' AS interval, trade_time FROM kline_week
            UNION ALL
            SELECT symbol, 'month' AS interval, trade_time FROM kline_month
            UNION ALL
            SELECT symbol, 'season' AS interval, trade_time FROM kline_season
            UNION ALL
            SELECT symbol, 'year' AS interval, trade_time FROM kline_year
        ) k
        GROUP BY k.symbol, k.interval
    """))

    # 3. 创建唯一索引（REFRESH MATERIALIZED VIEW CONCURRENTLY 需要）
    op.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_symbol_completeness "
        "ON mv_symbol_completeness (symbol, interval)"
    ))

    # 4. 扩展 completeness_check_results 表 — 状态机字段
    op.add_column(
        'completeness_check_results',
        sa.Column(
            'status',
            sa.String(length=20),
            server_default='pending',
            comment='状态: pending / confirmed_missing / repairing / repaired / repair_failed',
        ),
    )
    op.add_column(
        'completeness_check_results',
        sa.Column(
            'retry_count',
            sa.Integer(),
            server_default='0',
            comment='重试次数',
        ),
    )
    op.add_column(
        'completeness_check_results',
        sa.Column(
            'last_retry_at',
            sa.DateTime(),
            nullable=True,
            comment='最后重试时间',
        ),
    )
    op.create_index(
        'ix_completeness_check_results_status',
        'completeness_check_results',
        ['status'],
        unique=False,
    )


def downgrade() -> None:
    """回滚: 删除扩展列、MV、空数据缓存表."""

    op.drop_index(
        'ix_completeness_check_results_status',
        table_name='completeness_check_results',
    )
    op.drop_column('completeness_check_results', 'last_retry_at')
    op.drop_column('completeness_check_results', 'retry_count')
    op.drop_column('completeness_check_results', 'status')

    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS mv_symbol_completeness"))

    op.drop_index('idx_empty_data_cache_date', table_name='empty_data_cache')
    op.drop_table('empty_data_cache')
