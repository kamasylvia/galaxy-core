"""add_is_delisted_to_stock_basic

Revision ID: 77eed6cba408
Revises: 06_drop_empty_query
Create Date: 2026-06-03 10:28:20.480777

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77eed6cba408'
down_revision: Union[str, Sequence[str], None] = '06_drop_empty_query'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'stock_basic',
        sa.Column('is_delisted', sa.Boolean(), nullable=True, comment='是否已退市'),
    )
    op.create_index(
        'ix_stock_basic_is_delisted',
        'stock_basic',
        ['is_delisted'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_stock_basic_is_delisted', table_name='stock_basic')
    op.drop_column('stock_basic', 'is_delisted')
