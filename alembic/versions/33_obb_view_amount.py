"""obb_equity_historical view adds amount column.

单出口首切配套(2026-10-27):api 的 /prices /candles 切 OpenBB provider 后,
输出需与原 SQL 直读路径同形(含 amount)。视图 DROP+CREATE(OR REPLACE
不允许中间插列;视图无依赖者,重建安全)。

Revision ID: 33_obb_view_amount
Revises: 32_minute_is_final
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "33_obb_view_amount"
down_revision: str | Sequence[str] | None = "32_minute_is_final"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VIEW_OLD = """
CREATE VIEW obb_equity_historical AS
SELECT symbol, trade_time AS date, open, high, low, close, volume,
       CASE WHEN (volume > 0) THEN (amount / (volume)::numeric)
            ELSE NULL::numeric END AS vwap
FROM kline_day
"""

_VIEW_NEW = """
CREATE VIEW obb_equity_historical AS
SELECT symbol, trade_time AS date, open, high, low, close, volume, amount,
       CASE WHEN (volume > 0) THEN (amount / (volume)::numeric)
            ELSE NULL::numeric END AS vwap
FROM kline_day
"""


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS obb_equity_historical")
    op.execute(_VIEW_NEW)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS obb_equity_historical")
    op.execute(_VIEW_OLD)
