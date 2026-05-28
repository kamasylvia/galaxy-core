"""Drop market column from trading calendar

Revision ID: 002_drop_market_col
Revises: 001_update_market_field_length
Create Date: 2026-03-26 11:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers
revision = "002_drop_market_col"
down_revision = "001_update_market_field_length"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("trading_calendar")
        if constraint["name"]
    }
    columns = {column["name"] for column in inspector.get_columns("trading_calendar")}

    with op.batch_alter_table("trading_calendar") as batch_op:
        if "uq_market_trade_date" in unique_constraints:
            batch_op.drop_constraint("uq_market_trade_date", type_="unique")
        if "market" in columns:
            batch_op.drop_column("market")
        if "uq_trade_date" not in unique_constraints:
            batch_op.create_unique_constraint("uq_trade_date", ["trade_date"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("trading_calendar")
        if constraint["name"]
    }
    columns = {column["name"] for column in inspector.get_columns("trading_calendar")}

    with op.batch_alter_table("trading_calendar") as batch_op:
        if "uq_trade_date" in unique_constraints:
            batch_op.drop_constraint("uq_trade_date", type_="unique")
        if "market" not in columns:
            batch_op.add_column(
                sa.Column(
                    "market",
                    sa.String(length=50),
                    nullable=False,
                    server_default="SSE",
                )
            )
            batch_op.alter_column("market", server_default=None)
        if "uq_market_trade_date" not in unique_constraints:
            batch_op.create_unique_constraint(
                "uq_market_trade_date", ["market", "trade_date"]
            )
