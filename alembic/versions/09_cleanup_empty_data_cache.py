"""cleanup_empty_data_cache

Revision ID: 09_cleanup_empty_data_cache
Revises: 08_add_last_sync_date
Create Date: 2026-06-04 00:00:00.000000

清理 empty_data_cache 表：删除非 delisted 记录并删除 reason 列。

 downgrade 仅恢复 schema（添加 reason 列），不恢复已删除的数据。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '09_cleanup_empty_data_cache'
down_revision: Union[str, Sequence[str], None] = '08_add_last_sync_date'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """清理 empty_data_cache：删除非 delisted 记录并删除 reason 列."""
    inspector = inspect(op.get_bind())

    if inspector.has_table('empty_data_cache'):
        columns = {col['name'] for col in inspector.get_columns('empty_data_cache')}

        # 1. 删除非 delisted 记录（reason 列存在时）
        if 'reason' in columns:
            op.execute("DELETE FROM empty_data_cache WHERE reason != 'delisted'")

        # 2. 删除 reason 列（列存在时）
        if 'reason' in columns:
            op.drop_column('empty_data_cache', 'reason')


def downgrade() -> None:
    """恢复 reason 列（不恢复已删除数据）."""
    inspector = inspect(op.get_bind())

    if inspector.has_table('empty_data_cache'):
        columns = {col['name'] for col in inspector.get_columns('empty_data_cache')}

        if 'reason' not in columns:
            op.add_column(
                'empty_data_cache',
                sa.Column('reason', sa.String(length=20), nullable=True),
            )
