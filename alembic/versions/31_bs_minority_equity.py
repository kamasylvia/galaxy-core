"""Balance sheet minority equity for galaxy-web G1 (2026-10-22).

华发少股 ~900 亿: migration 30 只补了不含少股的权益,恒等式不平。
SDK 有 MINORITY_EQUITY + TOT_SHARE_EQUITY_INCL_MIN_INT(含少股总量),
勾稽 TOTAL_LIAB + INCL = TOTAL_ASSETS 精确成立(600325.SH 20260630 实测)。

- balance_sheet += minority_equity, tot_share_equity_incl_min_int
- backfill via CLI financial sync (UPSERT fills old rows).

Revision ID: 31_bs_minority_equity
Revises: 30_financial_gaps
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "31_bs_minority_equity"
down_revision: str | Sequence[str] | None = "30_financial_gaps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("balance_sheet", sa.Column("minority_equity", sa.Numeric(), nullable=True))
    op.add_column(
        "balance_sheet",
        sa.Column("tot_share_equity_incl_min_int", sa.Numeric(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("balance_sheet", "tot_share_equity_incl_min_int")
    op.drop_column("balance_sheet", "minority_equity")
