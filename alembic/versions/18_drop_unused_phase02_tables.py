"""drop unused phase 02 tables

Revision ID: 18_drop_unused_phase02_tables
Revises: 17_add_amazingdata_fund_flow
Create Date: 2026-06-19 00:00:00.000000

Phase 02 范围修订(2026-06-19, 见 .planning/phases/02-multi-source-fund-flow/02-SCOPE-REVISION-REPORT.md).

总纲从「跟着主力选股票/版块/ETF」收敛为「跟着主力选行业」(D-13).
删 7 张不再启用的表:
- akshare_market_fund_flow_daily   (大盘择时, 非选行业直接信号)
- akshare_stock_fund_flow_daily    (个股层, 粒度过细)
- akshare_north_fund_flow_daily    (北向总量, 无行业拆分)
- akshare_industry_pe_daily        (与 AmazingData industry_daily 重复, D-14)
- baostock_stock_valuation_daily   (baostock 整源删, D-15)
- baostock_macro_econ              (baostock 整源删, D-15)
- baostock_index_valuation_daily   (baostock 整源删, D-15)

保留 5 张启用表(下游依赖, 不动):
- akshare_sector_fund_flow_daily   (选行业核心)
- long_hu_bang / block_trading / margin_summary_daily / margin_detail_daily (AmazingData)

同步清理 sync_state 中 7 个 sync_type 的历史记录(D-17 未启用表不留状态).

downgrade 从 migration 15/16 git 历史复制 create_table 重建 schema(仅 schema, 历史数据不可恢复).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '18_drop_unused_phase02_tables'
down_revision: Union[str, Sequence[str], None] = '17_add_amazingdata_fund_flow'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 7 张待删表(按依赖反序 drop: 先 drop hypertable 子表无 FK, 顺序无强约束, 按字母逆序保险)
_UNUSED_TABLES = [
    'baostock_index_valuation_daily',
    'baostock_macro_econ',
    'baostock_stock_valuation_daily',
    'akshare_industry_pe_daily',
    'akshare_market_fund_flow_daily',
    'akshare_north_fund_flow_daily',
    'akshare_stock_fund_flow_daily',
]

# 7 个待清理 sync_type(与表一一对应)
_UNUSED_SYNC_TYPES = [
    'akshare_market_fund_flow',
    'akshare_stock_fund_flow',
    'akshare_north_fund_flow',
    'akshare_industry_pe',
    'baostock_stock_valuation',
    'baostock_macro',
    'baostock_index_valuation',
]


def upgrade() -> None:
    """drop 7 张未启用表 + 清理 sync_state."""
    bind = op.get_bind()
    inspector = inspect(bind)

    # 1. drop 表(每张先检查存在, 幂等)
    for table in _UNUSED_TABLES:
        if inspector.has_table(table):
            op.drop_table(table)

    # 2. 清理 sync_state 历史(7 个 sync_type)
    #    sync_state 表在 Phase 1 migration 已建, 此处假定存在; 用 raw SQL 批删
    sync_types_sql = ",".join(f"'{st}'" for st in _UNUSED_SYNC_TYPES)
    bind.execute(
        sa.text(f"DELETE FROM sync_state WHERE sync_type IN ({sync_types_sql})")
    )


def downgrade() -> None:
    """重建 7 张表 schema(从 migration 15/16 git 历史复制, 仅 schema 不含数据)."""
    inspector = inspect(op.get_bind())

    # --- akshare 4 表(原 migration 16) ---
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

    # --- baostock 3 表(原 migration 15, schema 完整复制) ---
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
