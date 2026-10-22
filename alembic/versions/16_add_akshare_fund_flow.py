"""add akshare fund flow tables

Revision ID: 16_add_akshare_fund_flow
Revises: 15_add_baostock_data
Create Date: 2026-06-18 00:00:00.000000

创建 5 张 akshare 资金流/行业 PE 表 (Phase 02):
- akshare_sector_fund_flow_daily: 板块资金流, PK (trade_date, sector_type, sector_name)
- akshare_stock_fund_flow_daily: 个股资金流, PK (symbol, trade_date)
- akshare_north_fund_flow_daily: 北向资金, PK (trade_date, channel)
- akshare_market_fund_flow_daily: 大盘资金流, PK (trade_date)
- akshare_industry_pe_daily: 申万行业指数 PE, PK (trade_date, industry_code) — D-12 由 baostock 迁入 akshare

各表 trade_date 用 sa.Date()(TimescaleDB hypertable 要求).
hypertable 在 init-db 流程中由 create_kline_hypertables 创建.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '16_add_akshare_fund_flow'
down_revision: Union[str, Sequence[str], None] = '15_add_baostock_data'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 5 张 akshare 资金流/行业 PE 表."""
    inspector = inspect(op.get_bind())

    # --- 板块资金流日数据 ---
    if not inspector.has_table('akshare_sector_fund_flow_daily'):
        op.create_table(
            'akshare_sector_fund_flow_daily',
            sa.Column('trade_date', sa.Date(), nullable=False, comment='交易日期'),
            sa.Column('sector_type', sa.String(length=50), nullable=False, comment='板块类型(行业/概念/地域)'),
            sa.Column('sector_name', sa.String(length=100), nullable=False, comment='板块名称'),
            sa.Column('pct_chg', sa.Float(), nullable=True, comment='今日涨跌幅(%)'),
            sa.Column('main_net_amount', sa.Float(), nullable=True, comment='主力净流入净额(元)'),
            sa.Column('main_net_pct', sa.Float(), nullable=True, comment='主力净流入净占比(%)'),
            sa.Column('super_large_net_amount', sa.Float(), nullable=True, comment='超大单净额(元)'),
            sa.Column('super_large_net_pct', sa.Float(), nullable=True, comment='超大单净占比(%)'),
            sa.Column('large_net_amount', sa.Float(), nullable=True, comment='大单净额(元)'),
            sa.Column('large_net_pct', sa.Float(), nullable=True, comment='大单净占比(%)'),
            sa.Column('medium_net_amount', sa.Float(), nullable=True, comment='中单净额(元)'),
            sa.Column('medium_net_pct', sa.Float(), nullable=True, comment='中单净占比(%)'),
            sa.Column('small_net_amount', sa.Float(), nullable=True, comment='小单净额(元)'),
            sa.Column('small_net_pct', sa.Float(), nullable=True, comment='小单净占比(%)'),
            sa.Column('top_stock', sa.String(length=100), nullable=True, comment='主力净流入最大股'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('trade_date', 'sector_type', 'sector_name', name='akshare_sector_fund_flow_daily_pkey'),
            sa.Index('ix_akshare_sector_fund_flow_daily_trade_date', 'trade_date'),
        )

    # --- 个股资金流日数据 ---
    if not inspector.has_table('akshare_stock_fund_flow_daily'):
        op.create_table(
            'akshare_stock_fund_flow_daily',
            sa.Column('symbol', sa.String(length=20), nullable=False, comment='证券代码'),
            sa.Column('trade_date', sa.Date(), nullable=False, comment='交易日期'),
            sa.Column('close', sa.Float(), nullable=True, comment='收盘价'),
            sa.Column('pct_chg', sa.Float(), nullable=True, comment='涨跌幅(%)'),
            sa.Column('main_net_amount', sa.Float(), nullable=True, comment='主力净额(元)'),
            sa.Column('main_net_pct', sa.Float(), nullable=True, comment='主力净占比(%)'),
            sa.Column('super_large_net_amount', sa.Float(), nullable=True, comment='超大单净额(元)'),
            sa.Column('super_large_net_pct', sa.Float(), nullable=True, comment='超大单净占比(%)'),
            sa.Column('large_net_amount', sa.Float(), nullable=True, comment='大单净额(元)'),
            sa.Column('large_net_pct', sa.Float(), nullable=True, comment='大单净占比(%)'),
            sa.Column('medium_net_amount', sa.Float(), nullable=True, comment='中单净额(元)'),
            sa.Column('medium_net_pct', sa.Float(), nullable=True, comment='中单净占比(%)'),
            sa.Column('small_net_amount', sa.Float(), nullable=True, comment='小单净额(元)'),
            sa.Column('small_net_pct', sa.Float(), nullable=True, comment='小单净占比(%)'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('symbol', 'trade_date', name='akshare_stock_fund_flow_daily_pkey'),
            sa.Index('ix_akshare_stock_fund_flow_daily_trade_date', 'trade_date'),
        )

    # --- 北向资金日数据 ---
    if not inspector.has_table('akshare_north_fund_flow_daily'):
        op.create_table(
            'akshare_north_fund_flow_daily',
            sa.Column('trade_date', sa.Date(), nullable=False, comment='交易日期'),
            sa.Column('channel', sa.String(length=20), nullable=False, comment='通道(北向资金/沪股通/深股通)'),
            sa.Column('inflow', sa.Float(), nullable=True, comment='当日资金流入(元)'),
            sa.Column('balance', sa.Float(), nullable=True, comment='当日余额(元)'),
            sa.Column('net_buy', sa.Float(), nullable=True, comment='成交净买额(元)'),
            sa.Column('hold_volume', sa.Float(), nullable=True, comment='持股总数(股)'),
            sa.Column('hold_value', sa.Float(), nullable=True, comment='持股市值(元)'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('trade_date', 'channel', name='akshare_north_fund_flow_daily_pkey'),
            sa.Index('ix_akshare_north_fund_flow_daily_trade_date', 'trade_date'),
        )

    # --- 大盘资金流日数据 ---
    if not inspector.has_table('akshare_market_fund_flow_daily'):
        op.create_table(
            'akshare_market_fund_flow_daily',
            sa.Column('trade_date', sa.Date(), nullable=False, comment='交易日期'),
            sa.Column('sh_close', sa.Float(), nullable=True, comment='上证收盘价'),
            sa.Column('sh_pct_chg', sa.Float(), nullable=True, comment='上证涨跌幅(%)'),
            sa.Column('sz_close', sa.Float(), nullable=True, comment='深证收盘价'),
            sa.Column('sz_pct_chg', sa.Float(), nullable=True, comment='深证涨跌幅(%)'),
            sa.Column('main_net_amount', sa.Float(), nullable=True, comment='主力净额(元)'),
            sa.Column('main_net_pct', sa.Float(), nullable=True, comment='主力净占比(%)'),
            sa.Column('super_large_net_amount', sa.Float(), nullable=True, comment='超大单净额(元)'),
            sa.Column('super_large_net_pct', sa.Float(), nullable=True, comment='超大单净占比(%)'),
            sa.Column('large_net_amount', sa.Float(), nullable=True, comment='大单净额(元)'),
            sa.Column('large_net_pct', sa.Float(), nullable=True, comment='大单净占比(%)'),
            sa.Column('medium_net_amount', sa.Float(), nullable=True, comment='中单净额(元)'),
            sa.Column('medium_net_pct', sa.Float(), nullable=True, comment='中单净占比(%)'),
            sa.Column('small_net_amount', sa.Float(), nullable=True, comment='小单净额(元)'),
            sa.Column('small_net_pct', sa.Float(), nullable=True, comment='小单净占比(%)'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('trade_date', name='akshare_market_fund_flow_daily_pkey'),
            sa.Index('ix_akshare_market_fund_flow_daily_trade_date', 'trade_date'),
        )

    # --- 申万行业指数 PE 日数据(D-12 由 baostock 迁入 akshare) ---
    if not inspector.has_table('akshare_industry_pe_daily'):
        op.create_table(
            'akshare_industry_pe_daily',
            sa.Column('trade_date', sa.Date(), nullable=False, comment='交易日期'),
            sa.Column('industry_code', sa.String(length=20), nullable=False, comment='申万行业代码'),
            sa.Column('industry_name', sa.String(length=100), nullable=True, comment='行业名称'),
            sa.Column('pe', sa.Float(), nullable=True, comment='行业市盈率'),
            sa.Column('pb', sa.Float(), nullable=True, comment='行业市净率'),
            sa.Column('close', sa.Float(), nullable=True, comment='行业指数收盘价'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('trade_date', 'industry_code', name='akshare_industry_pe_daily_pkey'),
            sa.Index('ix_akshare_industry_pe_daily_trade_date', 'trade_date'),
        )


def downgrade() -> None:
    """删除 5 张 akshare 资金流/行业 PE 表(反序)."""
    op.drop_table('akshare_industry_pe_daily')
    op.drop_table('akshare_market_fund_flow_daily')
    op.drop_table('akshare_north_fund_flow_daily')
    op.drop_table('akshare_stock_fund_flow_daily')
    op.drop_table('akshare_sector_fund_flow_daily')
