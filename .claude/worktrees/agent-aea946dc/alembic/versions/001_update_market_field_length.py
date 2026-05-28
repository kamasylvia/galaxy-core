"""Update market field length in trading calendar

Revision ID: 001_update_market_field_length
Revises:
Create Date: 2026-03-19 02:19:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_update_market_field_length'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update the market column length in trading_calendar table
    op.alter_column('trading_calendar', 'market',
                    type_=sa.String(50),
                    existing_type=sa.String(10))


def downgrade() -> None:
    # Revert the market column length in trading_calendar table
    op.alter_column('trading_calendar', 'market',
                    type_=sa.String(10),
                    existing_type=sa.String(50))
