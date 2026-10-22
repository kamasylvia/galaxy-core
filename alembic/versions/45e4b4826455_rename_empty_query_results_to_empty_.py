"""rename_empty_query_results_to_empty_query_caches

Revision ID: 45e4b4826455
Revises: 5ebbc3b25799
Create Date: 2026-05-28 16:09:40.466497

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '45e4b4826455'
down_revision: Union[str, Sequence[str], None] = '5ebbc3b25799'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table("empty_query_results", "empty_query_caches")


def downgrade() -> None:
    """Downgrade schema."""
    op.rename_table("empty_query_caches", "empty_query_results")
