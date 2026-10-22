"""replace_is_delisted_with_api_fields

Revision ID: 47922c8e5478
Revises: 77eed6cba408
Create Date: 2026-06-03 23:25:12.350044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47922c8e5478'
down_revision: Union[str, Sequence[str], None] = '77eed6cba408'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    1. 删除 is_delisted 列（含索引）
    2. 添加与 get_stock_basic API 对应的新字段
    """
    # 删除 is_delisted 索引和列
    op.drop_index('ix_stock_basic_is_delisted', table_name='stock_basic')
    op.drop_column('stock_basic', 'is_delisted')

    # 添加 API 对应字段
    op.add_column(
        'stock_basic',
        sa.Column('comp_name_eng', sa.String(length=200), nullable=True, comment='英文名称'),
    )
    op.add_column(
        'stock_basic',
        sa.Column('listplate_name', sa.String(length=50), nullable=True, comment='上市板块名称'),
    )
    op.add_column(
        'stock_basic',
        sa.Column('comp_sname_eng', sa.String(length=100), nullable=True, comment='英文名称缩写'),
    )
    op.add_column(
        'stock_basic',
        sa.Column(
            'is_listed',
            sa.Boolean(),
            nullable=True,
            comment='是否上市交易 (adapter转换: 1=True, 3=False)',
        ),
    )


def downgrade() -> None:
    """Downgrade schema.

    1. 删除新增字段
    2. 恢复 is_delisted 列（含索引）
    """
    op.drop_column('stock_basic', 'is_listed')
    op.drop_column('stock_basic', 'comp_sname_eng')
    op.drop_column('stock_basic', 'listplate_name')
    op.drop_column('stock_basic', 'comp_name_eng')

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
