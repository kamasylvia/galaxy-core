"""drop_empty_data_cache_completeness_log_stock_status

Revision ID: 0609b24d7754
Revises: 09_cleanup_empty_data_cache
Create Date: 2026-06-05 00:05:25.857098

删除废弃表：
- empty_data_cache: v1.3 后无人使用
- completeness_check_log: Phase 1 已删除代码，表遗漏
- stock_status: 当前仅 ETF，不预留
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '0609b24d7754'
down_revision: Union[str, Sequence[str], None] = '09_cleanup_empty_data_cache'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删除废弃表."""
    inspector = inspect(op.get_bind())

    # empty_data_cache
    if inspector.has_table('empty_data_cache'):
        indexes = {idx['name'] for idx in inspector.get_indexes('empty_data_cache')}
        if 'idx_empty_data_cache_date' in indexes:
            op.drop_index('idx_empty_data_cache_date', table_name='empty_data_cache')
        op.drop_table('empty_data_cache')

    # stock_status
    if inspector.has_table('stock_status'):
        indexes = {idx['name'] for idx in inspector.get_indexes('stock_status')}
        if 'idx_stock_status_date' in indexes:
            op.drop_index('idx_stock_status_date', table_name='stock_status')
        op.drop_table('stock_status')

    # completeness_check_log
    if inspector.has_table('completeness_check_log'):
        indexes = {idx['name'] for idx in inspector.get_indexes('completeness_check_log')}
        if 'idx_completeness_check_date' in indexes:
            op.drop_index('idx_completeness_check_date', table_name='completeness_check_log')
        if 'idx_completeness_check_type_date' in indexes:
            op.drop_index('idx_completeness_check_type_date', table_name='completeness_check_log')
        op.drop_table('completeness_check_log')


def downgrade() -> None:
    """重建表（不推荐回退）."""
    pass
