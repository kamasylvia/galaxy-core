"""add amazingdata fund flow tables

Revision ID: 17_add_amazingdata_fund_flow
Revises: 16_add_akshare_fund_flow
Create Date: 2026-06-18 00:00:00.000000

创建 4 张 AmazingData 资金流向表 (Phase 02):
- long_hu_bang: 龙虎榜, PK (market_code, trade_date, trader_name, flow_mark)
- block_trading: 大宗交易, PK (market_code, trade_date, b_buyer_name, b_seller_name)
- margin_summary_daily: 两融汇总, PK (trade_date)
- margin_detail_daily: 两融明细, PK (market_code, trade_date)

各表 trade_date 用 sa.Date()(TimescaleDB hypertable 要求).
flow_mark 用 sa.Integer()(PK 整型标记, 1=买/2=卖).
hypertable 在 init-db 流程中由 create_kline_hypertables 创建.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '17_add_amazingdata_fund_flow'
down_revision: Union[str, Sequence[str], None] = '16_add_akshare_fund_flow'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 4 张 AmazingData 资金流向表."""
    inspector = inspect(op.get_bind())

    # --- 龙虎榜日数据 ---
    if not inspector.has_table('long_hu_bang'):
        op.create_table(
            'long_hu_bang',
            sa.Column('market_code', sa.String(length=20), nullable=False, comment='证券代码'),
            sa.Column('trade_date', sa.Date(), nullable=False, comment='交易日期'),
            sa.Column('trader_name', sa.String(length=100), nullable=False, comment='营业部/席位名称'),
            sa.Column('flow_mark', sa.Integer(), nullable=False, comment='方向(1=买,2=卖)'),
            sa.Column('security_name', sa.String(length=100), nullable=True, comment='证券名称'),
            sa.Column('reason_type', sa.String(length=100), nullable=True, comment='入榜原因类型代码'),
            sa.Column('reason_type_name', sa.String(length=200), nullable=True, comment='入榜原因名称'),
            sa.Column('change_range', sa.Float(), nullable=True, comment='涨跌幅(%)'),
            sa.Column('buy_amount', sa.Float(), nullable=True, comment='买入额(元)'),
            sa.Column('sell_amount', sa.Float(), nullable=True, comment='卖出额(元)'),
            sa.Column('total_amount', sa.Float(), nullable=True, comment='成交总额(元)'),
            sa.Column('total_volume', sa.Float(), nullable=True, comment='成交总量(股)'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('market_code', 'trade_date', 'trader_name', 'flow_mark', name='long_hu_bang_pkey'),
            sa.Index('ix_long_hu_bang_trade_date', 'trade_date'),
        )

    # --- 大宗交易日数据 ---
    if not inspector.has_table('block_trading'):
        op.create_table(
            'block_trading',
            sa.Column('market_code', sa.String(length=20), nullable=False, comment='证券代码'),
            sa.Column('trade_date', sa.Date(), nullable=False, comment='交易日期'),
            sa.Column('b_buyer_name', sa.String(length=100), nullable=False, comment='买方营业部'),
            sa.Column('b_seller_name', sa.String(length=100), nullable=False, comment='卖方营业部'),
            sa.Column('b_share_price', sa.Float(), nullable=True, comment='成交价(元)'),
            sa.Column('b_share_volume', sa.Float(), nullable=True, comment='成交量(万股)'),
            sa.Column('b_frequency', sa.Integer(), nullable=True, comment='笔数'),
            sa.Column('block_avg_volume', sa.Float(), nullable=True, comment='每笔均量(股)'),
            sa.Column('b_share_amount', sa.Float(), nullable=True, comment='成交金额(万元)'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('market_code', 'trade_date', 'b_buyer_name', 'b_seller_name', name='block_trading_pkey'),
            sa.Index('ix_block_trading_trade_date', 'trade_date'),
        )

    # --- 两融汇总日数据 ---
    if not inspector.has_table('margin_summary_daily'):
        op.create_table(
            'margin_summary_daily',
            sa.Column('trade_date', sa.Date(), nullable=False, comment='交易日期'),
            sa.Column('sum_borrow_money_balance', sa.Float(), nullable=True, comment='融资余额(元)'),
            sa.Column('sum_purch_with_borrow_money', sa.Float(), nullable=True, comment='融资买入额(元)'),
            sa.Column('sum_repayment_of_borrow_money', sa.Float(), nullable=True, comment='融资偿还额(元)'),
            sa.Column('sum_sec_lending_balance', sa.Float(), nullable=True, comment='融券余额(元)'),
            sa.Column('sum_sales_of_borrowed_sec', sa.Float(), nullable=True, comment='融券卖出量(股)'),
            sa.Column('sum_margin_trade_balance', sa.Float(), nullable=True, comment='融资融券余额(元)'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('trade_date', name='margin_summary_daily_pkey'),
            sa.Index('ix_margin_summary_daily_trade_date', 'trade_date'),
        )

    # --- 两融明细日数据 ---
    if not inspector.has_table('margin_detail_daily'):
        op.create_table(
            'margin_detail_daily',
            sa.Column('market_code', sa.String(length=20), nullable=False, comment='证券代码'),
            sa.Column('trade_date', sa.Date(), nullable=False, comment='交易日期'),
            sa.Column('security_name', sa.String(length=100), nullable=True, comment='证券名称'),
            sa.Column('borrow_money_balance', sa.Float(), nullable=True, comment='融资余额(元)'),
            sa.Column('purch_with_borrow_money', sa.Float(), nullable=True, comment='融资买入额(元)'),
            sa.Column('repayment_of_borrow_money', sa.Float(), nullable=True, comment='融资偿还额(元)'),
            sa.Column('sec_lending_balance', sa.Float(), nullable=True, comment='融券余额(元)'),
            sa.Column('sales_of_borrowed_sec', sa.Float(), nullable=True, comment='融券卖出量(股)'),
            sa.Column('repayment_of_borrow_sec', sa.Float(), nullable=True, comment='融券偿还量(股)'),
            sa.Column('sec_lending_balance_vol', sa.Float(), nullable=True, comment='融券余量(股)'),
            sa.Column('margin_trade_balance', sa.Float(), nullable=True, comment='融资融券余额(元)'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('market_code', 'trade_date', name='margin_detail_daily_pkey'),
            sa.Index('ix_margin_detail_daily_trade_date', 'trade_date'),
        )


def downgrade() -> None:
    """删除 4 张 AmazingData 资金流向表(反序)."""
    op.drop_table('margin_detail_daily')
    op.drop_table('margin_summary_daily')
    op.drop_table('block_trading')
    op.drop_table('long_hu_bang')
