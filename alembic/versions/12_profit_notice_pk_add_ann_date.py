"""profit_notice PK 扩展为 (symbol, reporting_period, ann_date)

业绩预告数据同一 symbol 同一 reporting_period 可有多条记录
（首次预告、修正预告等），以 ann_date 区分。

Revision ID: 12_profit_notice_pk
Revises: 11_extend_last_sync_date
"""

from alembic import op

revision = "12_profit_notice_pk"
down_revision = "11_extend_last_sync_date"


def upgrade() -> None:
    op.drop_constraint("profit_notice_pkey", "profit_notice", type_="primary")
    op.alter_column("profit_notice", "ann_date", nullable=False)
    op.create_primary_key(
        "profit_notice_pkey", "profit_notice", ["symbol", "reporting_period", "ann_date"]
    )


def downgrade() -> None:
    op.drop_constraint("profit_notice_pkey", "profit_notice", type_="primary")
    op.alter_column("profit_notice", "ann_date", nullable=True)
    op.create_primary_key("profit_notice_pkey", "profit_notice", ["symbol", "reporting_period"])
