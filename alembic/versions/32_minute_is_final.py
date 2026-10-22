"""add is_final to 8 minute kline tables (realtime sub writes false, T+1 kline overwrites true).

Realtime subscription upserts unclosed bars (is_final=false); next-day
query_kline overwrites the same (symbol, trade_time) keys with final bars
(is_final=true). Frontend may filter for finalized bars.

Revision ID: 32_minute_is_final
Revises: 31_bs_minority_equity
"""

from collections.abc import Sequence

from alembic import op

revision: str = "32_minute_is_final"
down_revision: str | Sequence[str] | None = "31_bs_minority_equity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MINUTE_TABLES = [
    "kline_min1",
    "kline_min3",
    "kline_min5",
    "kline_min10",
    "kline_min15",
    "kline_min30",
    "kline_min60",
    "kline_min120",
]


def upgrade() -> None:
    for table in MINUTE_TABLES:
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS is_final BOOLEAN DEFAULT TRUE")


def downgrade() -> None:
    for table in MINUTE_TABLES:
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS is_final")
