"""merge migration branches

Revision ID: 380b224c6f6f
Revises: 02_drop_old_tables, 03_rename_bools
Create Date: 2026-06-01 14:58:33.604151

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '380b224c6f6f'
down_revision: Union[str, Sequence[str], None] = ('02_drop_old_tables', '03_rename_bools')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
