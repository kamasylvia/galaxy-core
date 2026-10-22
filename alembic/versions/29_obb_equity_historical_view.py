"""obb_equity_historical view for OpenBB provider (P2, 2026-10-21).

Finanalyzer openbb-hka Stock Price widget reads via provider
EquityHistorical fetcher; this view is the fetcher's sole source.
D5: vwap derived as amount/volume (no physical column).

Revision ID: 29_obb_equity_historical_view
Revises: 28_openbb_english_rename
"""

from collections.abc import Sequence

from alembic import op

revision: str = "29_obb_equity_historical_view"
down_revision: str | Sequence[str] | None = "28_openbb_english_rename"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW obb_equity_historical AS
        SELECT
            symbol,
            trade_time AS date,
            open, high, low, close, volume,
            CASE WHEN volume > 0 THEN amount / volume ELSE NULL END AS vwap
        FROM kline_day
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS obb_equity_historical")
