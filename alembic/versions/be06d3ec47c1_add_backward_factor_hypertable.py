"""add backward_factor hypertable

Revision ID: be06d3ec47c1
Revises: 5ebbc3b25799
Create Date: 2026-04-28 21:31:16.061625

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'be06d3ec47c1'
down_revision: Union[str, Sequence[str], None] = '5ebbc3b25799'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert backward_factor to TimescaleDB hypertable."""
    op.execute(
        "SELECT create_hypertable('backward_factor', 'trade_date', "
        "if_not_exists => true, migrate_data => true, "
        "chunk_time_interval => INTERVAL '1 year');"
    )


def downgrade() -> None:
    """Revert to regular table — not supported by TimescaleDB without table rebuild.

    Hypertable conversion is one-way; downgrade preserves hypertable state.
    """
    pass
