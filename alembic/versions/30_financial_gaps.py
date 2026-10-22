"""Financial statement gaps for galaxy-web Financials (2026-10-22).

galaxy-web W2: balance widget needs TOTAL_ASSETS/TOTAL_LIAB/equity.
SDK returns all (verified 600325.SH 20260630); model was narrow (17 cols).
income already has net_pro_excl_min_int_inc (归母净利润) — no change needed.

- balance_sheet += total_assets, total_liab, tot_share_equity_excl_min_int
- backfill via CLI financial sync (UPSERT fills old rows).

Revision ID: 30_financial_gaps
Revises: 29_obb_equity_historical_view
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "30_financial_gaps"
down_revision: str | Sequence[str] | None = "29_obb_equity_historical_view"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("balance_sheet", sa.Column("total_assets", sa.Numeric(), nullable=True))
    op.add_column("balance_sheet", sa.Column("total_liab", sa.Numeric(), nullable=True))
    op.add_column(
        "balance_sheet",
        sa.Column("tot_share_equity_excl_min_int", sa.Numeric(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("balance_sheet", "tot_share_equity_excl_min_int")
    op.drop_column("balance_sheet", "total_liab")
    op.drop_column("balance_sheet", "total_assets")
