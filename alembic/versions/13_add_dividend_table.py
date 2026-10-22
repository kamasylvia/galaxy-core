"""add dividend table

Revision ID: 13_add_dividend
Revises: 12_profit_notice_pk
Create Date: 2026-06-06 00:00:00.000000

创建分红配送表 (Phase 7):
- dividend: 分红配送, PK (symbol, reporting_period, ann_date)

添加 reporting_period 索引, 支持按报告期范围查询.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '13_add_dividend'
down_revision: Union[str, Sequence[str], None] = '12_profit_notice_pk'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建分红配送表."""
    inspector = inspect(op.get_bind())

    if not inspector.has_table('dividend'):
        op.create_table(
            'dividend',
            sa.Column('symbol', sa.String(length=20), nullable=False, comment='证券代码'),
            sa.Column('reporting_period', sa.String(length=8), nullable=False, comment='报告期 (YYYYMMDD)'),
            sa.Column('ann_date', sa.String(length=8), nullable=False, comment='公告日期 (YYYYMMDD)'),
            sa.Column('div_progress', sa.String(length=10), nullable=True, comment='实施进度 (1=预案, 3=已实施)'),
            sa.Column('dvd_per_share_stk', sa.Float(), nullable=True, comment='每股送股（股/股）'),
            sa.Column('dvd_per_share_pre_tax_cash', sa.Float(), nullable=True, comment='每股税前现金股利'),
            sa.Column('dvd_per_share_after_tax_cash', sa.Float(), nullable=True, comment='每股税后现金股利'),
            sa.Column('date_eqy_record', sa.String(length=8), nullable=True, comment='股权登记日'),
            sa.Column('date_ex', sa.String(length=8), nullable=True, comment='除权除息日'),
            sa.Column('date_dvd_payout', sa.String(length=8), nullable=True, comment='派息日'),
            sa.Column('listingdate_of_dvd_shr', sa.String(length=8), nullable=True, comment='红股上市日'),
            sa.Column('div_prelandate', sa.String(length=8), nullable=True, comment='预案公告日'),
            sa.Column('div_smtgdate', sa.String(length=8), nullable=True, comment='股东大会日期'),
            sa.Column('date_dvd_ann', sa.String(length=8), nullable=True, comment='分红公告日'),
            sa.Column('div_basedate', sa.String(length=8), nullable=True, comment='分红基准日'),
            sa.Column('div_baseshare', sa.Float(), nullable=True, comment='基准股本（万股）'),
            sa.Column('currency_code', sa.String(length=10), nullable=True, comment='货币代码'),
            sa.Column('is_changed', sa.Float(), nullable=True, comment='是否修正'),
            sa.Column('div_change', sa.Float(), nullable=True, comment='变动说明'),
            sa.Column('div_bonusrate', sa.Float(), nullable=True, comment='每股转增（股/股）'),
            sa.Column('div_conversedrate', sa.Float(), nullable=True, comment='送转比例'),
            sa.Column('remark', sa.String(length=2000), nullable=True, comment='备注'),
            sa.Column('div_preann_date', sa.String(length=8), nullable=True, comment='预案预披露日'),
            sa.Column('div_target', sa.String(length=100), nullable=True, comment='分红对象'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('symbol', 'reporting_period', 'ann_date', name='dividend_pkey'),
            sa.Index('ix_dividend_reporting_period', 'reporting_period'),
        )


def downgrade() -> None:
    """删除分红配送表."""
    op.drop_table('dividend')
