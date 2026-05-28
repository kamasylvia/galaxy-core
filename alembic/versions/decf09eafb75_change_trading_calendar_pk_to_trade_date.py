"""change_trading_calendar_pk_to_trade_date

Revision ID: decf09eafb75
Revises: ad91eb3c6441
Create Date: 2026-04-26 23:22:59.406916

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'decf09eafb75'
down_revision: Union[str, Sequence[str], None] = 'ad91eb3c6441'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop existing PK and id column
    op.drop_constraint('trading_calendar_pkey', 'trading_calendar', type_='primary')
    op.drop_column('trading_calendar', 'id')

    # Drop the old unique constraint (replaced by PK)
    op.drop_constraint('uq_trade_date', 'trading_calendar', type_='unique')

    # Add new PK on trade_date
    op.create_primary_key('trading_calendar_pkey', 'trading_calendar', ['trade_date'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop PK on trade_date
    op.drop_constraint('trading_calendar_pkey', 'trading_calendar', type_='primary')

    # Re-add id column
    op.add_column('trading_calendar', sa.Column('id', sa.Integer(), autoincrement=True, nullable=False))

    # Re-create unique constraint on trade_date
    op.create_unique_constraint('uq_trade_date', 'trading_calendar', ['trade_date'])

    # Re-create PK on id
    op.create_primary_key('trading_calendar_pkey', 'trading_calendar', ['id'])
