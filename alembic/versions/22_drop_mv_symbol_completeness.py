"""drop unused mv_symbol_completeness

Revision ID: 22_drop_mv_symbol_completeness
Revises: 21_fix_lsd_unique
Create Date: 2026-07-16 00:00:00.000000

删除未使用的 Materialized View mv_symbol_completeness。

背景:
该 MV 由 02_empty_data_cache_and_mv 创建，设计用途是「K线完整性 O(1) 查询」，
对应的读接口 SymbolCompletenessAdapter.get_completeness_summary 在代码库中
**零调用** —— 所有完整性判断走 KlineCompletenessChecker + trading_calendar 比对
+ last_sync_date，MV 从未被业务路径读取。

定时炸弹:
KlineSyncJob 每次同步后调 REFRESH MATERIALIZED VIEW CONCURRENTLY，需对 MV
底层所有 relation（5 张 kline hypertable × 数千 timescale chunk + 唯一索引）
加共享锁。生产 max_locks_per_transaction=64 × max_connections=100 远不够，
每次刷新必触 OutOfMemoryError（实测 2026-07-16 00:14 复现）。

D-22 设计让 refresh 失败被吞（不阻断同步），但 mv_symbol_completeness 永久陈旧。
既然无业务读取，删除 MV + 索引 + 全部相关代码。

downgrade 重建 MV（空数据，需手动 REFRESH）。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '22_drop_mv_symbol_completeness'
down_revision: Union[str, Sequence[str], None] = '21_fix_lsd_unique'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删除 mv_symbol_completeness + 唯一索引."""
    # PG DROP MATERIALIZED VIEW 会自动 CASCADE 依赖对象，但显式 drop index 更清晰。
    # 用 IF EXISTS 兜底（部分环境可能已被手动清理）。
    op.execute(
        text(
            "DROP MATERIALIZED VIEW IF EXISTS mv_symbol_completeness"
        )
    )


def downgrade() -> None:
    """重建 mv_symbol_completeness（空，需手动 REFRESH）."""
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
    op.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_symbol_completeness "
        "ON mv_symbol_completeness (symbol, interval)"
    ))
