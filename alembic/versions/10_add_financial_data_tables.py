"""add financial data tables

Revision ID: 10_add_financial_data
Revises: 0609b24d7754
Create Date: 2026-06-05 00:00:00.000000

创建 5 张财务数据表 (Phase 6):
- balance_sheet: 资产负债表, PK (symbol, reporting_period, statement_type)
- cash_flow: 现金流量表, PK (symbol, reporting_period, statement_type)
- income: 利润表, PK (symbol, reporting_period, statement_type)
- profit_express: 业绩快报, PK (symbol, reporting_period)
- profit_notice: 业绩预告, PK (symbol, reporting_period)

每张表添加 reporting_period 索引, 支持按报告期范围查询.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '10_add_financial_data'
down_revision: Union[str, Sequence[str], None] = '0609b24d7754'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_common_statement_columns() -> list:
    """三大报表公共列 (balance_sheet, cash_flow, income)."""
    return [
        sa.Column('symbol', sa.String(length=20), nullable=False, comment='证券代码'),
        sa.Column('security_name', sa.String(length=100), nullable=True, comment='证券简称'),
        sa.Column('statement_type', sa.String(length=10), nullable=False, comment='报表类型 (1-10)'),
        sa.Column('report_type', sa.String(length=10), nullable=True, comment='报告期名称 (1=3月, 2=6月, 3=9月, 4=12月)'),
        sa.Column('reporting_period', sa.String(length=8), nullable=False, comment='报告期 (YYYYMMDD)'),
        sa.Column('ann_date', sa.String(length=8), nullable=True, comment='公告日期'),
        sa.Column('actual_ann_date', sa.String(length=8), nullable=True, comment='实际公告日期'),
        sa.Column('comp_type_code', sa.String(length=10), nullable=True, comment='公司类型代码 (1=非金融, 2=银行, 3=保险, 4=证券)'),
    ]


def _create_timestamp_columns() -> list:
    """时间戳列."""
    return [
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
    ]


def upgrade() -> None:
    """创建 5 张财务数据表."""
    inspector = inspect(op.get_bind())

    # --- balance_sheet (资产负债表) ---
    if not inspector.has_table('balance_sheet'):
        op.create_table(
            'balance_sheet',
            *_create_common_statement_columns(),
            sa.Column('acc_payable', sa.Float(), nullable=True, comment='应付票据及应付账款'),
            sa.Column('acc_receivable', sa.Float(), nullable=True, comment='应收票据及应收账款'),
            sa.Column('acc_receivables', sa.Float(), nullable=True, comment='应收款项'),
            sa.Column('accrued_exp', sa.Float(), nullable=True, comment='预提费用'),
            sa.Column('acct_payable', sa.Float(), nullable=True, comment='应付账款'),
            sa.Column('acct_receivable', sa.Float(), nullable=True, comment='应收账款'),
            *_create_timestamp_columns(),
            sa.PrimaryKeyConstraint('symbol', 'reporting_period', 'statement_type'),
        )
        op.create_index(
            'ix_balance_sheet_reporting_period',
            'balance_sheet',
            ['reporting_period'],
        )

    # --- cash_flow (现金流量表) ---
    if not inspector.has_table('cash_flow'):
        op.create_table(
            'cash_flow',
            *_create_common_statement_columns(),
            sa.Column('absorb_cash_recp_inv', sa.Float(), nullable=True, comment='吸收投资收到的现金'),
            sa.Column('amort_intan_assets', sa.Float(), nullable=True, comment='无形资产摊销'),
            sa.Column('amort_lt_deferred_exp', sa.Float(), nullable=True, comment='长期待摊费用摊销'),
            sa.Column('beg_bal_cash_cash_equ', sa.Float(), nullable=True, comment='期初现金及现金等价物余额'),
            sa.Column('cash_end_bal', sa.Float(), nullable=True, comment='现金的期末余额'),
            sa.Column('cash_for_charge', sa.Float(), nullable=True, comment='支付手续费的现金'),
            sa.Column('cash_paid_insur_policy', sa.Float(), nullable=True, comment='支付保单红利的现金'),
            sa.Column('cash_paid_inv', sa.Float(), nullable=True, comment='投资支付的现金'),
            sa.Column('cash_paid_pur_const_fiolta', sa.Float(), nullable=True, comment='购建固定资产、无形资产和其他长期资产支付的现金'),
            sa.Column('cash_pay_claims_oic', sa.Float(), nullable=True, comment='支付原保险合同赔付款项的现金'),
            sa.Column('cash_pay_dist_div_pro_int', sa.Float(), nullable=True, comment='分配股利、利润或偿付利息支付的现金'),
            sa.Column('cash_pay_employee', sa.Float(), nullable=True, comment='支付给职工以及为职工支付的现金'),
            sa.Column('cash_pay_for_debt', sa.Float(), nullable=True, comment='偿还债务支付的现金'),
            sa.Column('cash_pay_goods_services', sa.Float(), nullable=True, comment='购买商品、接受劳务支付的现金'),
            sa.Column('cash_rece_borrow', sa.Float(), nullable=True, comment='取得借款收到的现金'),
            sa.Column('cash_rece_issue_bonds', sa.Float(), nullable=True, comment='发行债券收到的现金'),
            sa.Column('cash_recp_inv_income', sa.Float(), nullable=True, comment='取得投资收益收到的现金'),
            sa.Column('cash_recp_prem_oic', sa.Float(), nullable=True, comment='收到原保险合同保费取得的现金'),
            sa.Column('cash_recp_recov_inv', sa.Float(), nullable=True, comment='收回投资收到的现金'),
            sa.Column('cash_recp_sg_and_rs', sa.Float(), nullable=True, comment='销售商品、提供劳务收到的现金'),
            sa.Column('conv_corp_bonds_due_within_1y', sa.Float(), nullable=True, comment='一年内到期的可转换公司债券'),
            sa.Column('conv_debt_into_cap', sa.Float(), nullable=True, comment='债务转为资本'),
            sa.Column('credit_impair_loss', sa.Float(), nullable=True, comment='信用减值损失'),
            sa.Column('currency_code', sa.String(length=10), nullable=True, comment='货币代码'),
            sa.Column('decr_deferred_tax_assets', sa.Float(), nullable=True, comment='递延所得税资产减少'),
            sa.Column('decr_deferred_expense', sa.Float(), nullable=True, comment='待摊费用减少'),
            sa.Column('decr_inventory', sa.Float(), nullable=True, comment='存货的减少'),
            sa.Column('decr_opera_receivable', sa.Float(), nullable=True, comment='经营性应收项目的减少'),
            sa.Column('depre_fa_oga_pba', sa.Float(), nullable=True, comment='固定资产折旧、油气资产折耗、生产性生物资产折旧'),
            sa.Column('eff_fx_fluc_cash', sa.Float(), nullable=True, comment='汇率变动对现金的影响'),
            sa.Column('end_bal_cash_cash_equ', sa.Float(), nullable=True, comment='期末现金及现金等价物余额'),
            sa.Column('financial_exp', sa.Float(), nullable=True, comment='财务费用'),
            sa.Column('fixed_assets_fin_lease', sa.Float(), nullable=True, comment='融资租入固定资产'),
            sa.Column('free_cash_flow', sa.Float(), nullable=True, comment='企业自由现金流量'),
            sa.Column('incl_cash_recp_saims', sa.Float(), nullable=True, comment='其中:子公司吸收少数股东投资收到的现金'),
            sa.Column('incl_div_pro_paid_sms', sa.Float(), nullable=True, comment='其中:子公司支付给少数股东的股利、利润'),
            sa.Column('incr_accrued_exp', sa.Float(), nullable=True, comment='预提费用增加'),
            sa.Column('incr_deferred_tax_liab', sa.Float(), nullable=True, comment='递延所得税负债增加'),
            sa.Column('incr_opera_payable', sa.Float(), nullable=True, comment='经营性应付项目的增加'),
            sa.Column('ind_net_cash_flows_opera_act', sa.Float(), nullable=True, comment='间接法-经营活动产生的现金流量净额'),
            sa.Column('ind_net_incr_cash_and_equ', sa.Float(), nullable=True, comment='间接法-现金及现金等价物净增加额'),
            sa.Column('inv_loss', sa.Float(), nullable=True, comment='投资损失'),
            sa.Column('is_calculation', sa.Float(), nullable=True, comment='是否计算报表'),
            sa.Column('less_open_bal_cash', sa.Float(), nullable=True, comment='减:现金的期初余额'),
            sa.Column('less_open_bal_cash_equ', sa.Float(), nullable=True, comment='减:现金等价物的期初余额'),
            sa.Column('loss_disp_fiolta', sa.Float(), nullable=True, comment='处置固定、无形资产和其他长期资产的损失'),
            sa.Column('loss_fairvalue_chg', sa.Float(), nullable=True, comment='公允价值变动损失'),
            sa.Column('loss_fixed_assets', sa.Float(), nullable=True, comment='固定资产报废损失'),
            sa.Column('net_cash_flows_fin_act', sa.Float(), nullable=True, comment='筹资活动产生的现金流量净额'),
            sa.Column('net_cash_flows_inv_act', sa.Float(), nullable=True, comment='投资活动产生的现金流量净额'),
            sa.Column('net_cash_flows_opera_act', sa.Float(), nullable=True, comment='经营活动产生的现金流量净额'),
            sa.Column('net_cash_paid_sobu', sa.Float(), nullable=True, comment='取得子公司及其他营业单位支付的现金净额'),
            sa.Column('net_cash_rec_sec', sa.Float(), nullable=True, comment='代理买卖证券收到的现金净额'),
            sa.Column('net_cash_recp_disp_fiolta', sa.Float(), nullable=True, comment='处置固定资产、无形资产和其他长期资产收回的现金净额'),
            sa.Column('net_cash_recp_disp_sobu', sa.Float(), nullable=True, comment='处置子公司及其他营业单位收到的现金净额'),
            sa.Column('net_cash_recp_reinsu_bus', sa.Float(), nullable=True, comment='收到再保业务现金净额'),
            sa.Column('net_incr_borr_fund', sa.Float(), nullable=True, comment='拆入资金净增加额'),
            sa.Column('net_incr_borr_ofi', sa.Float(), nullable=True, comment='向其他金融机构拆入资金净增加额'),
            sa.Column('net_incr_cash_and_cash_equ', sa.Float(), nullable=True, comment='现金及现金等价物净增加额'),
            sa.Column('net_incr_cus_loan_adv', sa.Float(), nullable=True, comment='客户贷款及垫款净增加额'),
            sa.Column('net_incr_dep_cb_ib', sa.Float(), nullable=True, comment='存放央行和同业款项净增加额'),
            sa.Column('net_incr_dep_cus_and_ib', sa.Float(), nullable=True, comment='客户存款和同业存放款项净增加额'),
            sa.Column('net_incr_dismantle_cap', sa.Float(), nullable=True, comment='拆出资金净增加额'),
            sa.Column('net_incr_disp_faas', sa.Float(), nullable=True, comment='处置可供出售金融资产净增加额'),
            sa.Column('net_incr_disp_tfa', sa.Float(), nullable=True, comment='处置交易性金融资产净增加额'),
            sa.Column('net_incr_insured_save', sa.Float(), nullable=True, comment='保户储金净增加额'),
            sa.Column('net_incr_int_and_charge', sa.Float(), nullable=True, comment='收取利息和手续费净增加额'),
            sa.Column('net_incr_loans_central_bank', sa.Float(), nullable=True, comment='向中央银行借款净增加额'),
            sa.Column('net_incr_pledge_loan', sa.Float(), nullable=True, comment='质押贷款净增加额'),
            sa.Column('net_incr_repu_bus_fund', sa.Float(), nullable=True, comment='回购业务资金净增加额'),
            sa.Column('net_profit', sa.Float(), nullable=True, comment='净利润'),
            sa.Column('oth_cash_pay_inv_act', sa.Float(), nullable=True, comment='支付其他与投资活动有关的现金'),
            sa.Column('oth_cash_pay_opera_act', sa.Float(), nullable=True, comment='支付其他与经营活动有关的现金'),
            sa.Column('oth_cash_recp_inv_act', sa.Float(), nullable=True, comment='收到其他与投资活动有关的现金'),
            sa.Column('other_assets_impair_loss', sa.Float(), nullable=True, comment='其他资产减值损失'),
            sa.Column('other_cash_pay_fin_act', sa.Float(), nullable=True, comment='支付其他与筹资活动有关的现金'),
            sa.Column('other_cash_recp_fin_act', sa.Float(), nullable=True, comment='收到其他与筹资活动有关的现金'),
            sa.Column('other_cash_recp_oper_act', sa.Float(), nullable=True, comment='收到其他与经营活动有关的现金'),
            sa.Column('others', sa.Float(), nullable=True, comment='其他（废弃）'),
            sa.Column('pay_all_tax', sa.Float(), nullable=True, comment='支付的各项税费'),
            sa.Column('plus_assets_depre_prep', sa.Float(), nullable=True, comment='加:资产减值准备'),
            sa.Column('plus_end_bal_cash_equ', sa.Float(), nullable=True, comment='加:现金等价物的期末余额'),
            sa.Column('recp_tax_refund', sa.Float(), nullable=True, comment='收到的税费返还'),
            sa.Column('use_right_asset_dep', sa.Float(), nullable=True, comment='使用权资产折旧'),
            *_create_timestamp_columns(),
            sa.PrimaryKeyConstraint('symbol', 'reporting_period', 'statement_type'),
        )
        op.create_index(
            'ix_cash_flow_reporting_period',
            'cash_flow',
            ['reporting_period'],
        )

    # --- income (利润表) ---
    if not inspector.has_table('income'):
        op.create_table(
            'income',
            *_create_common_statement_columns(),
            sa.Column('amort_cost_fin_assets_ear', sa.Float(), nullable=True, comment='以摊余成本计量的金融资产终止确认收益'),
            sa.Column('basic_eps', sa.Float(), nullable=True, comment='基本每股收益'),
            sa.Column('beg_undistributed_pro', sa.Float(), nullable=True, comment='年初未分配利润'),
            sa.Column('capitalized_com_stock_div', sa.Float(), nullable=True, comment='转作股本的普通股股利'),
            sa.Column('comments', sa.String(length=500), nullable=True, comment='备注'),
            sa.Column('common_stock_div_payable', sa.Float(), nullable=True, comment='应付普通股股利'),
            sa.Column('continued_net_opera_pro', sa.Float(), nullable=True, comment='持续经营净利润'),
            sa.Column('credit_impair_loss', sa.Float(), nullable=True, comment='信用减值损失'),
            sa.Column('currency_code', sa.String(length=10), nullable=True, comment='货币代码'),
            sa.Column('diluted_eps', sa.Float(), nullable=True, comment='稀释每股收益'),
            sa.Column('distributive_pro', sa.Float(), nullable=True, comment='可分配利润'),
            sa.Column('distributive_pro_shareholder', sa.Float(), nullable=True, comment='可供股东分配的利润'),
            sa.Column('div_exp_insur', sa.Float(), nullable=True, comment='保户红利支出'),
            sa.Column('ebit', sa.Float(), nullable=True, comment='息税前利润 (正向法)'),
            sa.Column('ebitda', sa.Float(), nullable=True, comment='息税折旧摊销前利润'),
            sa.Column('employee_welfare', sa.Float(), nullable=True, comment='职工奖金福利'),
            sa.Column('end_net_opera_pro', sa.Float(), nullable=True, comment='终止经营净利润'),
            sa.Column('ext_insur_cont_rsrv', sa.Float(), nullable=True, comment='提取保险责任准备金'),
            sa.Column('ext_unearned_prem_res', sa.Float(), nullable=True, comment='提取未到期责任准备金'),
            sa.Column('fin_exp_int_exp', sa.Float(), nullable=True, comment='财务费用:利息费用'),
            sa.Column('fin_exp_int_inc', sa.Float(), nullable=True, comment='财务费用:利息收入'),
            sa.Column('gain_disposal_assets', sa.Float(), nullable=True, comment='资产处置收益'),
            sa.Column('handling_chrg_comm_fee', sa.Float(), nullable=True, comment='手续费及佣金收入'),
            sa.Column('incl_inc_inv_jv_entp', sa.Float(), nullable=True, comment='其中:对联营企业和合营企业的投资收益'),
            sa.Column('incl_less_loss_disp_ncur_asset', sa.Float(), nullable=True, comment='其中:减:非流动资产处置净损失'),
            sa.Column('incl_reinsur_prem_inc', sa.Float(), nullable=True, comment='其中:分保费收入'),
            sa.Column('income_tax', sa.Float(), nullable=True, comment='所得税'),
            sa.Column('insur_exp', sa.Float(), nullable=True, comment='保险业务支出'),
            sa.Column('insur_prem', sa.Float(), nullable=True, comment='已赚保费'),
            sa.Column('interest_inc', sa.Float(), nullable=True, comment='利息收入'),
            sa.Column('is_calculation', sa.Float(), nullable=True, comment='是否计算报表'),
            sa.Column('less_admin_exp', sa.Float(), nullable=True, comment='减:管理费用'),
            sa.Column('less_amort_compen_exp', sa.Float(), nullable=True, comment='减:摊回赔付支出'),
            sa.Column('less_amort_insur_cont_rsrv', sa.Float(), nullable=True, comment='减:摊回保险责任准备金'),
            sa.Column('less_amort_reinsur_exp', sa.Float(), nullable=True, comment='减:摊回分保费用'),
            sa.Column('less_assets_impair_loss', sa.Float(), nullable=True, comment='减:资产减值损失'),
            sa.Column('less_bus_tax_surcharge', sa.Float(), nullable=True, comment='减:营业税金及附加'),
            sa.Column('less_fin_exp', sa.Float(), nullable=True, comment='减:财务费用'),
            sa.Column('less_handling_chrg_comm_fee', sa.Float(), nullable=True, comment='减:手续费及佣金支出'),
            sa.Column('less_interest_exp', sa.Float(), nullable=True, comment='减:利息支出'),
            sa.Column('less_non_opera_exp', sa.Float(), nullable=True, comment='减:营业外支出'),
            sa.Column('less_opera_cost', sa.Float(), nullable=True, comment='减:营业成本'),
            sa.Column('less_reinsur_prem', sa.Float(), nullable=True, comment='减:分出保费'),
            sa.Column('less_selling_exp', sa.Float(), nullable=True, comment='减:销售费用'),
            sa.Column('min_int_inc', sa.Float(), nullable=True, comment='少数股东损益'),
            sa.Column('net_exposure_hedging_gain', sa.Float(), nullable=True, comment='净敞口套期收益'),
            sa.Column('net_handling_chrg_comm_fee', sa.Float(), nullable=True, comment='手续费及佣金净收入'),
            sa.Column('net_inc_ec_asset_mgmt_bus', sa.Float(), nullable=True, comment='受托客户资产管理业务净收入'),
            sa.Column('net_inc_sec_brok_bus', sa.Float(), nullable=True, comment='代理买卖证券业务净收入'),
            sa.Column('net_inc_sec_uw_bus', sa.Float(), nullable=True, comment='证券承销业务净收入'),
            sa.Column('net_interest_inc', sa.Float(), nullable=True, comment='利息净收入'),
            sa.Column('net_pro_after_ded_nr_gl', sa.Float(), nullable=True, comment='扣除非经常性损益后净利润（扣除少数股东损益）'),
            sa.Column('net_pro_after_ded_nr_gl_cor', sa.Float(), nullable=True, comment='扣除非经常性损益后的净利润(财务重要指标(更正前))'),
            sa.Column('net_pro_excl_min_int_inc', sa.Float(), nullable=True, comment='净利润(不含少数股东损益)'),
            sa.Column('net_pro_incl_min_int_inc', sa.Float(), nullable=True, comment='净利润(含少数股东损益)'),
            sa.Column('net_pro_under_int_acc_sta', sa.Float(), nullable=True, comment='国际会计准则净利润'),
            sa.Column('opera_exp', sa.Float(), nullable=True, comment='营业支出'),
            sa.Column('opera_profit', sa.Float(), nullable=True, comment='营业利润'),
            sa.Column('opera_rev', sa.Float(), nullable=True, comment='营业收入'),
            sa.Column('oth_assets_impair_loss', sa.Float(), nullable=True, comment='其他资产减值损失'),
            sa.Column('oth_bus_cost', sa.Float(), nullable=True, comment='其他业务成本'),
            sa.Column('oth_bus_inc', sa.Float(), nullable=True, comment='其他业务收入'),
            sa.Column('oth_compre_inc', sa.Float(), nullable=True, comment='其他综合收益'),
            sa.Column('oth_income', sa.Float(), nullable=True, comment='其他收益'),
            sa.Column('oth_net_opera_inc', sa.Float(), nullable=True, comment='其他经营净收益'),
            sa.Column('plus_net_fx_inc', sa.Float(), nullable=True, comment='加:汇兑净收益'),
            sa.Column('plus_net_gain_chg_fv', sa.Float(), nullable=True, comment='加:公允价值变动净收益'),
            sa.Column('plus_net_inv_inc', sa.Float(), nullable=True, comment='加:投资净收益'),
            sa.Column('plus_non_opera_rev', sa.Float(), nullable=True, comment='加:营业外收入'),
            sa.Column('plus_oth_net_bus_inc', sa.Float(), nullable=True, comment='加:其他业务净收益'),
            sa.Column('preferred_share_div_payable', sa.Float(), nullable=True, comment='应付优先股股利'),
            sa.Column('prem_bus_inc', sa.Float(), nullable=True, comment='保费业务收入'),
            sa.Column('rd_exp', sa.Float(), nullable=True, comment='研发费用'),
            sa.Column('reinsurance_exp', sa.Float(), nullable=True, comment='分保费用'),
            sa.Column('spe_bal_net_pro_marg', sa.Float(), nullable=True, comment='净利润差额(特殊报表科目)'),
            sa.Column('spe_bal_opera_pro_marg', sa.Float(), nullable=True, comment='营业利润差额(特殊报表科目)'),
            sa.Column('spe_bal_tot_opera_cost_dif', sa.Float(), nullable=True, comment='营业总成本差额(特殊报表科目)'),
            sa.Column('spe_bal_tot_opera_inc_dif', sa.Float(), nullable=True, comment='营业总收入差额(特殊报表科目)'),
            sa.Column('spe_bal_tot_pro_marg', sa.Float(), nullable=True, comment='利润总额差额(特殊报表科目)'),
            sa.Column('spe_tot_opera_cost_dif_state', sa.String(length=500), nullable=True, comment='营业总成本差额说明(特殊报表科目)'),
            sa.Column('spe_tot_opera_inc_dif_state', sa.String(length=500), nullable=True, comment='营业总收入差额说明(特殊报表科目)'),
            sa.Column('surr_value', sa.Float(), nullable=True, comment='退保金'),
            sa.Column('tot_bal_net_pro_marg', sa.Float(), nullable=True, comment='净利润差额(合计平衡项目)'),
            sa.Column('tot_bal_opera_pro_marg', sa.Float(), nullable=True, comment='营业利润差额(合计平衡项目)'),
            sa.Column('tot_bal_tot_pro_marg', sa.Float(), nullable=True, comment='利润总额差额(合计平衡项目)'),
            sa.Column('tot_compen_exp', sa.Float(), nullable=True, comment='赔付总支出'),
            sa.Column('tot_compre_inc', sa.Float(), nullable=True, comment='综合收益总额'),
            sa.Column('tot_compre_inc_min_share', sa.Float(), nullable=True, comment='综合收益总额(少数股东)'),
            sa.Column('tot_compre_inc_parent_comp', sa.Float(), nullable=True, comment='综合收益总额(母公司)'),
            sa.Column('tot_opera_cost', sa.Float(), nullable=True, comment='营业总成本'),
            sa.Column('tot_opera_cost2', sa.Float(), nullable=True, comment='营业总成本2'),
            sa.Column('tot_opera_rev', sa.Float(), nullable=True, comment='营业总收入'),
            sa.Column('total_profit', sa.Float(), nullable=True, comment='利润总额'),
            sa.Column('transfer_housing_revo_funds', sa.Float(), nullable=True, comment='住房周转金转入'),
            sa.Column('transfer_others', sa.Float(), nullable=True, comment='其他转入'),
            sa.Column('transfer_surplus_reserve', sa.Float(), nullable=True, comment='盈余公积转入'),
            sa.Column('unconfirmed_inv_loss', sa.Float(), nullable=True, comment='未确认投资损失'),
            sa.Column('withdraw_any_surplus_resv', sa.Float(), nullable=True, comment='提取任意盈余公积金'),
            sa.Column('withdraw_ent_develop_fund', sa.Float(), nullable=True, comment='提取企业发展基金'),
            sa.Column('withdraw_leg_pub_wel_fund', sa.Float(), nullable=True, comment='提取法定公益金'),
            sa.Column('withdraw_leg_surplus', sa.Float(), nullable=True, comment='提取法定盈余公积'),
            sa.Column('withdraw_resv_fund', sa.Float(), nullable=True, comment='提取储备基金'),
            *_create_timestamp_columns(),
            sa.PrimaryKeyConstraint('symbol', 'reporting_period', 'statement_type'),
        )
        op.create_index(
            'ix_income_reporting_period',
            'income',
            ['reporting_period'],
        )

    # --- profit_express (业绩快报) ---
    if not inspector.has_table('profit_express'):
        op.create_table(
            'profit_express',
            sa.Column('symbol', sa.String(length=20), nullable=False, comment='证券代码'),
            sa.Column('reporting_period', sa.String(length=8), nullable=False, comment='报告期 (YYYYMMDD)'),
            sa.Column('ann_date', sa.String(length=8), nullable=True, comment='公告日期'),
            sa.Column('actual_ann_date', sa.String(length=8), nullable=True, comment='实际公告日期'),
            sa.Column('total_assets', sa.Float(), nullable=True, comment='总资产(元)'),
            sa.Column('net_pro_excl_min_int_inc', sa.Float(), nullable=True, comment='净利润(元) — 归母净利润'),
            sa.Column('tot_opera_rev', sa.Float(), nullable=True, comment='营业总收入(元)'),
            sa.Column('total_profit', sa.Float(), nullable=True, comment='利润总额(元)'),
            sa.Column('opera_profit', sa.Float(), nullable=True, comment='营业利润(元)'),
            sa.Column('eps_basic', sa.Float(), nullable=True, comment='每股收益-基本(元)'),
            sa.Column('tot_share_equity_excl_min_int', sa.Float(), nullable=True, comment='股东权益合计(不含少数股东权益)(元)'),
            sa.Column('is_audit', sa.Float(), nullable=True, comment='是否审计 (1=是, 0=否)'),
            sa.Column('roe_weighted', sa.Float(), nullable=True, comment='净资产收益率-加权(%)'),
            sa.Column('last_year_revised_net_pro', sa.Float(), nullable=True, comment='去年同期修正后净利润(元)'),
            sa.Column('performance_summary', sa.String(length=2000), nullable=True, comment='业绩简要说明'),
            sa.Column('net_asset_ps', sa.Float(), nullable=True, comment='每股净资产(元)'),
            sa.Column('memo', sa.String(length=500), nullable=True, comment='备注'),
            sa.Column('yoy_gr_gross_pro', sa.Float(), nullable=True, comment='同比增长率:营业利润(%)'),
            sa.Column('yoy_gr_gross_rev', sa.Float(), nullable=True, comment='同比增长率:营业总收入(%)'),
            sa.Column('yoy_gr_net_profit_parent', sa.Float(), nullable=True, comment='同比增长率:归属母公司股东的净利润(%)'),
            sa.Column('yoy_gr_tot_pro', sa.Float(), nullable=True, comment='同比增长率:利润总额(%)'),
            sa.Column('yoy_id_waroe', sa.Float(), nullable=True, comment='同比增减:加权平均净资产收益率(%)'),
            sa.Column('yoy_gr_eps_basic', sa.Float(), nullable=True, comment='同比增长率:基本每股收益(%)'),
            sa.Column('growth_rate_equity', sa.Float(), nullable=True, comment='比年初增长率:归属母公司的股东权益(%)'),
            sa.Column('growth_rate_assets', sa.Float(), nullable=True, comment='比年初增长率:总资产(%)'),
            sa.Column('growth_rate_naps', sa.Float(), nullable=True, comment='比年初增长率:归属于母公司股东的每股净资产(%)'),
            sa.Column('last_year_tot_opera_rev', sa.Float(), nullable=True, comment='去年同期营业总收入(元)'),
            sa.Column('last_year_total_profit', sa.Float(), nullable=True, comment='去年同期利润总额(元)'),
            sa.Column('last_year_opera_pro', sa.Float(), nullable=True, comment='去年同期营业利润(元)'),
            sa.Column('last_year_eps_diluted', sa.Float(), nullable=True, comment='去年同期每股收益(元)'),
            sa.Column('last_year_net_profit', sa.Float(), nullable=True, comment='去年同期净利润(元)'),
            sa.Column('initial_net_asset_ps', sa.Float(), nullable=True, comment='期初每股净资产(元)'),
            sa.Column('initial_net_assets', sa.Float(), nullable=True, comment='期初净资产(元)'),
            *_create_timestamp_columns(),
            sa.PrimaryKeyConstraint('symbol', 'reporting_period'),
        )
        op.create_index(
            'ix_profit_express_reporting_period',
            'profit_express',
            ['reporting_period'],
        )

    # --- profit_notice (业绩预告) ---
    if not inspector.has_table('profit_notice'):
        op.create_table(
            'profit_notice',
            sa.Column('symbol', sa.String(length=20), nullable=False, comment='证券代码'),
            sa.Column('security_name', sa.String(length=100), nullable=True, comment='证券简称'),
            sa.Column('reporting_period', sa.String(length=8), nullable=False, comment='报告期 (YYYYMMDD)'),
            sa.Column('ann_date', sa.String(length=8), nullable=True, comment='公告日期'),
            sa.Column('p_typecode', sa.String(length=10), nullable=True, comment='业绩预告类型代码 (1-11)'),
            sa.Column('report_type', sa.String(length=10), nullable=True, comment='报告期名称 (1=3月, 2=6月, 3=9月, 4=12月)'),
            sa.Column('p_change_max', sa.Float(), nullable=True, comment='预告净利润变动幅度上限(%)'),
            sa.Column('p_change_min', sa.Float(), nullable=True, comment='预告净利润变动幅度下限(%)'),
            sa.Column('net_profit_max', sa.Float(), nullable=True, comment='预告净利润上限(万元)'),
            sa.Column('net_profit_min', sa.Float(), nullable=True, comment='预告净利润下限(万元)'),
            sa.Column('first_ann_date', sa.String(length=8), nullable=True, comment='首次公告日'),
            sa.Column('p_number', sa.Float(), nullable=True, comment='公布次数'),
            sa.Column('p_reason', sa.String(length=2000), nullable=True, comment='业绩变动原因'),
            sa.Column('p_summary', sa.String(length=2000), nullable=True, comment='业绩预告摘要'),
            sa.Column('p_net_parent_firm', sa.Float(), nullable=True, comment='上年同期归母净利润(万元)'),
            *_create_timestamp_columns(),
            sa.PrimaryKeyConstraint('symbol', 'reporting_period'),
        )
        op.create_index(
            'ix_profit_notice_reporting_period',
            'profit_notice',
            ['reporting_period'],
        )


def downgrade() -> None:
    """删除 5 张财务数据表 (逆序)."""
    inspector = inspect(op.get_bind())

    tables = [
        'profit_notice',
        'profit_express',
        'income',
        'cash_flow',
        'balance_sheet',
    ]

    for table in tables:
        indexes = {idx['name'] for idx in inspector.get_indexes(table)} if inspector.has_table(table) else set()
        ix_name = f'ix_{table}_reporting_period'
        if ix_name in indexes:
            op.drop_index(ix_name, table_name=table)

    for table in tables:
        if inspector.has_table(table):
            op.drop_table(table)
