"""rename_stock_status_bools_to_match_api

Revision ID: 03_rename_bools
Revises: 02_drop_old_tables
Create Date: 2026-06-01 14:43:00.000000

D-03b/D-10/D-11/D-12: 重命名 stock_status 布尔字段以匹配 AmazingData API 字段名。
- is_st     -> is_st_sec     (是否 ST)
- is_susp   -> is_susp_sec   (是否停牌)
- is_xr     -> is_xr_sec     (是否除权)
- is_wd     -> is_wd_sec     (是否除息)

symbol 保留为内部字段名（D-03b），不重命名。
PostgreSQL RENAME COLUMN 是元数据操作，保留索引和约束。
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '03_rename_bools'
down_revision: Union[str, Sequence[str], None] = '02_drop_old_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """重命名 stock_status 布尔字段以匹配 API 字段名."""
    op.alter_column("stock_status", "is_st", new_column_name="is_st_sec")
    op.alter_column("stock_status", "is_susp", new_column_name="is_susp_sec")
    op.alter_column("stock_status", "is_xr", new_column_name="is_xr_sec")
    op.alter_column("stock_status", "is_wd", new_column_name="is_wd_sec")


def downgrade() -> None:
    """回滚: 恢复原始布尔字段名."""
    op.alter_column("stock_status", "is_st_sec", new_column_name="is_st")
    op.alter_column("stock_status", "is_susp_sec", new_column_name="is_susp")
    op.alter_column("stock_status", "is_xr_sec", new_column_name="is_xr")
    op.alter_column("stock_status", "is_wd_sec", new_column_name="is_wd")
