"""add baostock data tables

Revision ID: 15_add_baostock_data
Revises: 14_add_index_data
Create Date: 2026-06-18 00:00:00.000000

创建 3 张 baostock 数据表 (Phase 02):
- baostock_stock_valuation_daily: 个股估值日数据, PK (symbol, trade_date)
- baostock_macro_econ: 宏观经济指标, PK (date) — deviation(02-01): 删 CPI/PPI/GDP, 加 loan_rate_1y/reserve_ratio
- baostock_index_valuation_daily: 指数估值日数据, PK (index_code, trade_date)

各表 trade_date/date 用 sa.Date()(TimescaleDB hypertable 要求).
hypertable 在 init-db 流程中由 create_kline_hypertables 创建.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '15_add_baostock_data'
down_revision: Union[str, Sequence[str], None] = '14_add_index_data'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 3 张 baostock 数据表."""
    inspector = inspect(op.get_bind())

    # --- 个股估值日数据 ---
    if not inspector.has_table('baostock_stock_valuation_daily'):
        op.create_table(
            'baostock_stock_valuation_daily',
            sa.Column('symbol', sa.String(length=20), nullable=False, comment='证券代码'),
            sa.Column('trade_date', sa.Date(), nullable=False, comment='交易日期'),
            sa.Column('pe_ttm', sa.Float(), nullable=True, comment='滚动市盈率'),
            sa.Column('pb_mr', sa.Float(), nullable=True, comment='市净率'),
            sa.Column('ps_ttm', sa.Float(), nullable=True, comment='滚动市销率'),
            sa.Column('pcf_ttm', sa.Float(), nullable=True, comment='滚动市现率'),
            sa.Column('turn', sa.Float(), nullable=True, comment='换手率(%)'),
            sa.Column('is_st', sa.Integer(), nullable=True, comment='是否 ST(1=是,0=否)'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('symbol', 'trade_date', name='baostock_stock_valuation_daily_pkey'),
            sa.Index('ix_baostock_stock_valuation_daily_trade_date', 'trade_date'),
        )

    # --- 宏观经济指标(deviation 02-01: 删 CPI/PPI/GDP, 加 loan_rate_1y/reserve_ratio) ---
    if not inspector.has_table('baostock_macro_econ'):
        op.create_table(
            'baostock_macro_econ',
            sa.Column('date', sa.Date(), nullable=False, comment='统计日期(month/year 接口由 store adapter 规范化)'),
            sa.Column('m0', sa.Float(), nullable=True, comment='流通中现金(M0)'),
            sa.Column('m1', sa.Float(), nullable=True, comment='狭义货币(M1)'),
            sa.Column('m2', sa.Float(), nullable=True, comment='广义货币(M2)'),
            sa.Column('deposit_rate_1y', sa.Float(), nullable=True, comment='1 年期存款利率(%)'),
            sa.Column('loan_rate_1y', sa.Float(), nullable=True, comment='1 年期贷款利率(%)'),
            sa.Column('reserve_ratio', sa.Float(), nullable=True, comment='存款准备金率(%)'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('date', name='baostock_macro_econ_pkey'),
            sa.Index('ix_baostock_macro_econ_date', 'date'),
        )

    # --- 指数估值日数据 ---
    if not inspector.has_table('baostock_index_valuation_daily'):
        op.create_table(
            'baostock_index_valuation_daily',
            sa.Column('index_code', sa.String(length=20), nullable=False, comment='指数代码'),
            sa.Column('trade_date', sa.Date(), nullable=False, comment='交易日期'),
            sa.Column('pe_ttm', sa.Float(), nullable=True, comment='滚动市盈率'),
            sa.Column('pb_mr', sa.Float(), nullable=True, comment='市净率'),
            sa.Column('turn', sa.Float(), nullable=True, comment='换手率(%)'),
            sa.Column('close', sa.Float(), nullable=True, comment='收盘价'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('index_code', 'trade_date', name='baostock_index_valuation_daily_pkey'),
            sa.Index('ix_baostock_index_valuation_daily_trade_date', 'trade_date'),
        )


def downgrade() -> None:
    """删除 3 张 baostock 数据表(反序)."""
    op.drop_table('baostock_index_valuation_daily')
    op.drop_table('baostock_macro_econ')
    op.drop_table('baostock_stock_valuation_daily')
