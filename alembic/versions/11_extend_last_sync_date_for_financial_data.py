"""extend last_sync_date for financial data

Revision ID: 11_extend_last_sync_date
Revises: 10_add_financial_data
Create Date: 2026-06-05 00:00:00.000000

扩展 last_sync_date 表支持财务数据同步:
- 添加自增 id 列作为新主键
- 添加 data_type 列（nullable, varchar(20)）
- interval 列改为 nullable（财务数据行此列为 NULL）
- 替换原 PrimaryKeyConstraint(symbol, interval) 为 UniqueConstraint
- 添加 UniqueConstraint(symbol, data_type)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision: str = '11_extend_last_sync_date'
down_revision: Union[str, Sequence[str], None] = '10_add_financial_data'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """扩展 last_sync_date 表."""
    inspector = inspect(op.get_bind())

    if not inspector.has_table('last_sync_date'):
        # 表不存在（全新部署）— ORM 模型定义会自动创建正确结构
        # 这里仅创建完整表供 alembic upgrade 使用
        op.create_table(
            'last_sync_date',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('symbol', sa.String(length=20), nullable=False, comment='证券代码'),
            sa.Column('interval', sa.String(length=20), nullable=True, comment='K 线周期'),
            sa.Column('data_type', sa.String(length=20), nullable=True, comment='财务数据类型'),
            sa.Column(
                'last_sync_date', sa.Date(),
                nullable=False, comment='最后同步交易日期/报告期',
            ),
            sa.Column(
                'updated_at',
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
                comment='记录更新时间 (UTC)',
            ),
            sa.PrimaryKeyConstraint('id', name='pk_last_sync_date_id'),
            sa.UniqueConstraint('symbol', 'interval', name='uq_last_sync_date_symbol_interval'),
            sa.UniqueConstraint('symbol', 'data_type', name='uq_last_sync_date_symbol_data_type'),
        )
        return

    # --- 表已存在，需要迁移 ---

    # 1. 先删除原主键约束（interval 是主键列，不能先 DROP NOT NULL）
    pk_constraints = inspector.get_pk_constraint('last_sync_date')
    pk_name = pk_constraints.get('name') if pk_constraints else None
    if pk_name:
        op.drop_constraint(pk_name, 'last_sync_date', type_='primary')
    else:
        op.drop_constraint('last_sync_date_pkey', 'last_sync_date', type_='primary')

    # 2. 添加 id 列（使用 SERIAL 自动创建序列）
    columns = {col['name'] for col in inspector.get_columns('last_sync_date')}
    if 'id' not in columns:
        op.execute(text(
            "ALTER TABLE last_sync_date ADD COLUMN id SERIAL"
        ))

    # 3. 添加 data_type 列
    if 'data_type' not in columns:
        op.add_column(
            'last_sync_date',
            sa.Column(
                'data_type',
                sa.String(length=20),
                nullable=True,
                comment='财务数据类型',
            ),
        )

    # 4. 将 interval 列改为 nullable
    op.alter_column(
        'last_sync_date', 'interval',
        existing_type=sa.String(length=20),
        nullable=True,
    )

    # 5. 回填 id 值（SERIAL 已创建序列 last_sync_date_id_seq）
    op.execute(text(
        "UPDATE last_sync_date SET id = nextval('last_sync_date_id_seq'::regclass) "
        "WHERE id IS NULL"
    ))

    # 6. 将 id 列设为 NOT NULL
    op.alter_column(
        'last_sync_date', 'id',
        existing_type=sa.Integer(),
        nullable=False,
    )

    # 7. 添加新主键约束
    op.create_primary_key('pk_last_sync_date_id', 'last_sync_date', ['id'])

    # 8. 添加 UniqueConstraint(symbol, data_type)
    unique_constraints = {
        uc['name'] for uc in inspector.get_unique_constraints('last_sync_date')
    }
    if 'uq_last_sync_date_symbol_data_type' not in unique_constraints:
        op.create_unique_constraint(
            'uq_last_sync_date_symbol_data_type',
            'last_sync_date',
            ['symbol', 'data_type'],
        )

    # 9. 原 (symbol, interval) 主键 → UniqueConstraint
    if 'uq_last_sync_date_symbol_interval' not in unique_constraints:
        op.create_unique_constraint(
            'uq_last_sync_date_symbol_interval',
            'last_sync_date',
            ['symbol', 'interval'],
        )


def downgrade() -> None:
    """还原 last_sync_date 表结构."""
    inspector = inspect(op.get_bind())

    if not inspector.has_table('last_sync_date'):
        return

    unique_constraints = {
        uc['name'] for uc in inspector.get_unique_constraints('last_sync_date')
    }
    columns = {col['name'] for col in inspector.get_columns('last_sync_date')}

    # 1. 删除新添加的 UniqueConstraint
    if 'uq_last_sync_date_symbol_interval' in unique_constraints:
        op.drop_constraint(
            'uq_last_sync_date_symbol_interval',
            'last_sync_date',
            type_='unique',
        )
    if 'uq_last_sync_date_symbol_data_type' in unique_constraints:
        op.drop_constraint(
            'uq_last_sync_date_symbol_data_type',
            'last_sync_date',
            type_='unique',
        )

    # 2. 删除新主键
    pk_constraints = inspector.get_pk_constraint('last_sync_date')
    pk_name = pk_constraints.get('name') if pk_constraints else None
    if pk_name:
        op.drop_constraint(pk_name, 'last_sync_date', type_='primary')

    # 3. 删除 id 列
    if 'id' in columns:
        op.drop_column('last_sync_date', 'id')

    # 4. 删除 data_type 列
    if 'data_type' in columns:
        op.drop_column('last_sync_date', 'data_type')

    # 5. interval 改回 NOT NULL
    op.alter_column(
        'last_sync_date', 'interval',
        existing_type=sa.String(length=20),
        nullable=False,
    )

    # 6. 恢复原 PrimaryKeyConstraint(symbol, interval)
    op.create_primary_key('last_sync_date_pkey', 'last_sync_date', ['symbol', 'interval'])
