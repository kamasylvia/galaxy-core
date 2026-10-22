"""merge heads

Revision ID: cc36b7ffea14
Revises: 380b224c6f6f, be06d3ec47c1
Create Date: 2026-06-02 00:33:14.797519

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc36b7ffea14'
down_revision: Union[str, Sequence[str], None] = ('380b224c6f6f', 'be06d3ec47c1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
