"""add index data tables

Revision ID: 14_add_index_data
Revises: 97d8c6124869
Create Date: 2026-06-15 00:00:00.000000

创建 6 张指数数据表 (Phase: 交易所指数 + 行业指数):
- index_constituent: 交易所指数成分股, PK (index_code, con_code, in_date)
- index_weight: 交易所指数日权重, PK (index_code, con_code, trade_date)
- industry_base_info: 行业指数基本信息, PK (index_code, industry_code)
- industry_constituent: 行业指数成分股, PK (index_code, con_code, in_date)
- industry_weight: 行业指数日权重, PK (index_code, con_code, trade_date)
- industry_daily: 行业指数日行情, PK (index_code, trade_date) — TimescaleDB hypertable

各表添加索引，支持按指数代码/交易日期范围查询.
industry_daily 的 hypertable 在 init-db 流程中由 create_kline_hypertables 创建.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '14_add_index_data'
down_revision: Union[str, Sequence[str], None] = '97d8c6124869'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 6 张指数数据表."""
    inspector = inspect(op.get_bind())

    # --- 交易所指数成分股 ---
    if not inspector.has_table('index_constituent'):
        op.create_table(
            'index_constituent',
            sa.Column('index_code', sa.String(length=20), nullable=False, comment='指数代码'),
            sa.Column('con_code', sa.String(length=20), nullable=False, comment='成分股代码'),
            sa.Column('in_date', sa.String(length=8), nullable=False, comment='纳入日期 (YYYYMMDD)'),
            sa.Column('out_date', sa.String(length=8), nullable=True, comment='剔除日期 (YYYYMMDD)，未剔除为 NULL'),
            sa.Column('index_name', sa.String(length=100), nullable=True, comment='指数名称'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('index_code', 'con_code', 'in_date', name='index_constituent_pkey'),
            sa.Index('ix_index_constituent_index_code', 'index_code'),
        )

    # --- 交易所指数日权重 (SDK 仅支持 5 个指数) ---
    if not inspector.has_table('index_weight'):
        op.create_table(
            'index_weight',
            sa.Column('index_code', sa.String(length=20), nullable=False, comment='指数代码'),
            sa.Column('con_code', sa.String(length=20), nullable=False, comment='成分股代码'),
            sa.Column('trade_date', sa.String(length=8), nullable=False, comment='生效日期 (YYYYMMDD)'),
            sa.Column('total_share', sa.Float(), nullable=True, comment='总股本（股）'),
            sa.Column('free_share_ratio', sa.Float(), nullable=True, comment='自由流通比例（%）'),
            sa.Column('calc_share', sa.Float(), nullable=True, comment='计算用股本（股）'),
            sa.Column('weight_factor', sa.Float(), nullable=True, comment='权重因子'),
            sa.Column('weight', sa.Float(), nullable=True, comment='权重（%）'),
            sa.Column('close', sa.Float(), nullable=True, comment='收盘价'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('index_code', 'con_code', 'trade_date', name='index_weight_pkey'),
            sa.Index('ix_index_weight_trade_date', 'trade_date'),
        )

    # --- 行业指数基本信息 ---
    if not inspector.has_table('industry_base_info'):
        op.create_table(
            'industry_base_info',
            sa.Column('index_code', sa.String(length=20), nullable=False, comment='行业指数代码'),
            sa.Column('industry_code', sa.String(length=20), nullable=False, comment='行业代码'),
            sa.Column('level_type', sa.Integer(), nullable=True, comment='指数类别 (1=一级, 2=二级, 3=三级)'),
            sa.Column('level1_name', sa.String(length=100), nullable=True, comment='一级行业'),
            sa.Column('level2_name', sa.String(length=100), nullable=True, comment='二级行业'),
            sa.Column('level3_name', sa.String(length=100), nullable=True, comment='三级行业'),
            sa.Column('is_pub', sa.Integer(), nullable=True, comment='是否发布 (1=已发布, 2=未发布)'),
            sa.Column('change_reason', sa.String(length=200), nullable=True, comment='变动原因'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('index_code', 'industry_code', name='industry_base_info_pkey'),
            sa.Index('ix_industry_base_info_level_type', 'level_type'),
        )

    # --- 行业指数成分股 ---
    if not inspector.has_table('industry_constituent'):
        op.create_table(
            'industry_constituent',
            sa.Column('index_code', sa.String(length=20), nullable=False, comment='行业指数代码'),
            sa.Column('con_code', sa.String(length=20), nullable=False, comment='成分股代码'),
            sa.Column('in_date', sa.String(length=8), nullable=False, comment='纳入日期 (YYYYMMDD)'),
            sa.Column('out_date', sa.String(length=8), nullable=True, comment='剔除日期 (YYYYMMDD)，未剔除为 NULL'),
            sa.Column('index_name', sa.String(length=100), nullable=True, comment='指数名称'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('index_code', 'con_code', 'in_date', name='industry_constituent_pkey'),
            sa.Index('ix_industry_constituent_index_code', 'index_code'),
        )

    # --- 行业指数日权重 ---
    if not inspector.has_table('industry_weight'):
        op.create_table(
            'industry_weight',
            sa.Column('index_code', sa.String(length=20), nullable=False, comment='行业指数代码'),
            sa.Column('con_code', sa.String(length=20), nullable=False, comment='成分股代码'),
            sa.Column('trade_date', sa.String(length=8), nullable=False, comment='交易日期 (YYYYMMDD)'),
            sa.Column('weight', sa.Float(), nullable=True, comment='权重'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('index_code', 'con_code', 'trade_date', name='industry_weight_pkey'),
            sa.Index('ix_industry_weight_trade_date', 'trade_date'),
        )

    # --- 行业指数日行情 (hypertable 由 init-db 后续创建) ---
    if not inspector.has_table('industry_daily'):
        op.create_table(
            'industry_daily',
            sa.Column('index_code', sa.String(length=20), nullable=False, comment='行业指数代码'),
            sa.Column('trade_date', sa.Date(), nullable=False, comment='交易日期'),
            sa.Column('open', sa.Float(), nullable=True, comment='开盘价'),
            sa.Column('high', sa.Float(), nullable=True, comment='最高价'),
            sa.Column('low', sa.Float(), nullable=True, comment='最低价'),
            sa.Column('close', sa.Float(), nullable=True, comment='收盘价'),
            sa.Column('pre_close', sa.Float(), nullable=True, comment='昨收盘价'),
            sa.Column('volume', sa.Float(), nullable=True, comment='成交量（股）'),
            sa.Column('amount', sa.Float(), nullable=True, comment='成交金额（元）'),
            sa.Column('pb', sa.Float(), nullable=True, comment='指数市净率'),
            sa.Column('pe', sa.Float(), nullable=True, comment='指数市盈率'),
            sa.Column('total_cap', sa.Float(), nullable=True, comment='总市值（万元）'),
            sa.Column('a_float_cap', sa.Float(), nullable=True, comment='A股流通市值（万元）'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('index_code', 'trade_date', name='industry_daily_pkey'),
            sa.Index('ix_industry_daily_trade_date', 'trade_date'),
        )


def downgrade() -> None:
    """删除 6 张指数数据表（按创建逆序）."""
    op.drop_table('industry_daily')
    op.drop_table('industry_weight')
    op.drop_table('industry_constituent')
    op.drop_table('industry_base_info')
    op.drop_table('index_weight')
    op.drop_table('index_constituent')
