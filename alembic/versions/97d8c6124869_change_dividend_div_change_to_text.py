"""change dividend div_change to text

Revision ID: 97d8c6124869
Revises: 13_add_dividend
Create Date: 2026-06-06 14:18:05.934782

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '97d8c6124869'
down_revision: str | Sequence[str] | None = '13_add_dividend'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('dividend', 'div_change',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               type_=sa.String(length=4000),
               existing_comment='变动说明',
               existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('dividend', 'div_change',
               existing_type=sa.String(length=4000),
               type_=sa.DOUBLE_PRECISION(precision=53),
               existing_comment='变动说明',
               existing_nullable=True)
