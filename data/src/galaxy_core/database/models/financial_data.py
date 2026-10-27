"""AUTO-GENERATED from nocodb schema(2026-08-26 回迁 P4).

生成器: scripts/nocodb_reimport/gen_models.py。表名=nocodb 中文表名;
业务列名=原 pg 列名;NocoDB 系统列应用不写。
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from .kline import Base


class BalanceSheet(Base):
    """表 "balance_sheet"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "balance_sheet"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    symbol: Mapped[str] = mapped_column(Text, primary_key=True)
    security_name: Mapped[str | None] = mapped_column(Text)
    statement_type: Mapped[str] = mapped_column(Text, primary_key=True)
    report_type: Mapped[str | None] = mapped_column(Text)
    reporting_period: Mapped[date] = mapped_column(Date, primary_key=True)
    ann_date: Mapped[date | None] = mapped_column(Date)
    actual_ann_date: Mapped[date | None] = mapped_column(Date)
    comp_type_code: Mapped[str | None] = mapped_column(Text)
    total_assets: Mapped[Decimal | None] = mapped_column(Numeric)
    total_liab: Mapped[Decimal | None] = mapped_column(Numeric)
    tot_share_equity_excl_min_int: Mapped[Decimal | None] = mapped_column(Numeric)
    tot_share_equity_incl_min_int: Mapped[Decimal | None] = mapped_column(Numeric)
    minority_equity: Mapped[Decimal | None] = mapped_column(Numeric)
    acc_payable: Mapped[Decimal | None] = mapped_column(Numeric)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<BalanceSheet(symbol={self.symbol!r}"
            f", reporting_period={self.reporting_period!r}"
            f", statement_type={self.statement_type!r})>"
        )


class CashFlow(Base):
    """表 "cash_flow"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "cash_flow"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    symbol: Mapped[str] = mapped_column(Text, primary_key=True)
    security_name: Mapped[str | None] = mapped_column(Text)
    statement_type: Mapped[str] = mapped_column(Text, primary_key=True)
    report_type: Mapped[str | None] = mapped_column(Text)
    reporting_period: Mapped[date] = mapped_column(Date, primary_key=True)
    ann_date: Mapped[date | None] = mapped_column(Date)
    actual_ann_date: Mapped[date | None] = mapped_column(Date)
    comp_type_code: Mapped[str | None] = mapped_column(Text)
    absorb_cash_recp_inv: Mapped[Decimal | None] = mapped_column(Numeric)
    amort_intan_assets: Mapped[Decimal | None] = mapped_column(Numeric)
    amort_lt_deferred_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    beg_bal_cash_cash_equ: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_end_bal: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_for_charge: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_paid_insur_policy: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_paid_inv: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_paid_pur_const_fiolta: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_pay_claims_oic: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_pay_dist_div_pro_int: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_pay_employee: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_pay_for_debt: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_pay_goods_services: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_rece_borrow: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_rece_issue_bonds: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_recp_inv_income: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_recp_prem_oic: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_recp_recov_inv: Mapped[Decimal | None] = mapped_column(Numeric)
    cash_recp_sg_and_rs: Mapped[Decimal | None] = mapped_column(Numeric)
    conv_corp_bonds_due_within_1y: Mapped[Decimal | None] = mapped_column(Numeric)
    conv_debt_into_cap: Mapped[Decimal | None] = mapped_column(Numeric)
    credit_impair_loss: Mapped[Decimal | None] = mapped_column(Numeric)
    currency_code: Mapped[str | None] = mapped_column(Text)
    decr_deferred_tax_assets: Mapped[Decimal | None] = mapped_column(Numeric)
    decr_deferred_expense: Mapped[Decimal | None] = mapped_column(Numeric)
    decr_inventory: Mapped[Decimal | None] = mapped_column(Numeric)
    decr_opera_receivable: Mapped[Decimal | None] = mapped_column(Numeric)
    depre_fa_oga_pba: Mapped[Decimal | None] = mapped_column(Numeric)
    eff_fx_fluc_cash: Mapped[Decimal | None] = mapped_column(Numeric)
    end_bal_cash_cash_equ: Mapped[Decimal | None] = mapped_column(Numeric)
    financial_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    fixed_assets_fin_lease: Mapped[Decimal | None] = mapped_column(Numeric)
    free_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric)
    incl_cash_recp_saims: Mapped[Decimal | None] = mapped_column(Numeric)
    incl_div_pro_paid_sms: Mapped[Decimal | None] = mapped_column(Numeric)
    incr_accrued_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    incr_deferred_tax_liab: Mapped[Decimal | None] = mapped_column(Numeric)
    incr_opera_payable: Mapped[Decimal | None] = mapped_column(Numeric)
    ind_net_cash_flows_opera_act: Mapped[Decimal | None] = mapped_column(Numeric)
    ind_net_incr_cash_and_equ: Mapped[Decimal | None] = mapped_column(Numeric)
    inv_loss: Mapped[Decimal | None] = mapped_column(Numeric)
    is_calculation: Mapped[Decimal | None] = mapped_column(Numeric)
    less_open_bal_cash: Mapped[Decimal | None] = mapped_column(Numeric)
    less_open_bal_cash_equ: Mapped[Decimal | None] = mapped_column(Numeric)
    loss_disp_fiolta: Mapped[Decimal | None] = mapped_column(Numeric)
    loss_fairvalue_chg: Mapped[Decimal | None] = mapped_column(Numeric)
    loss_fixed_assets: Mapped[Decimal | None] = mapped_column(Numeric)
    net_cash_flows_fin_act: Mapped[Decimal | None] = mapped_column(Numeric)
    net_cash_flows_inv_act: Mapped[Decimal | None] = mapped_column(Numeric)
    net_cash_flows_opera_act: Mapped[Decimal | None] = mapped_column(Numeric)
    net_cash_paid_sobu: Mapped[Decimal | None] = mapped_column(Numeric)
    net_cash_rec_sec: Mapped[Decimal | None] = mapped_column(Numeric)
    net_cash_recp_disp_fiolta: Mapped[Decimal | None] = mapped_column(Numeric)
    net_cash_recp_disp_sobu: Mapped[Decimal | None] = mapped_column(Numeric)
    net_cash_recp_reinsu_bus: Mapped[Decimal | None] = mapped_column(Numeric)
    net_incr_borr_fund: Mapped[Decimal | None] = mapped_column(Numeric)
    net_incr_borr_ofi: Mapped[Decimal | None] = mapped_column(Numeric)
    net_incr_cash_and_cash_equ: Mapped[Decimal | None] = mapped_column(Numeric)
    net_incr_cus_loan_adv: Mapped[Decimal | None] = mapped_column(Numeric)
    net_incr_dep_cb_ib: Mapped[Decimal | None] = mapped_column(Numeric)
    net_incr_dep_cus_and_ib: Mapped[Decimal | None] = mapped_column(Numeric)
    net_incr_dismantle_cap: Mapped[Decimal | None] = mapped_column(Numeric)
    net_incr_disp_faas: Mapped[Decimal | None] = mapped_column(Numeric)
    net_incr_disp_tfa: Mapped[Decimal | None] = mapped_column(Numeric)
    net_incr_insured_save: Mapped[Decimal | None] = mapped_column(Numeric)
    net_incr_int_and_charge: Mapped[Decimal | None] = mapped_column(Numeric)
    net_incr_loans_central_bank: Mapped[Decimal | None] = mapped_column(Numeric)
    net_incr_pledge_loan: Mapped[Decimal | None] = mapped_column(Numeric)
    net_incr_repu_bus_fund: Mapped[Decimal | None] = mapped_column(Numeric)
    net_profit: Mapped[Decimal | None] = mapped_column(Numeric)
    oth_cash_pay_inv_act: Mapped[Decimal | None] = mapped_column(Numeric)
    oth_cash_pay_opera_act: Mapped[Decimal | None] = mapped_column(Numeric)
    oth_cash_recp_inv_act: Mapped[Decimal | None] = mapped_column(Numeric)
    other_assets_impair_loss: Mapped[Decimal | None] = mapped_column(Numeric)
    other_cash_pay_fin_act: Mapped[Decimal | None] = mapped_column(Numeric)
    other_cash_recp_fin_act: Mapped[Decimal | None] = mapped_column(Numeric)
    other_cash_recp_oper_act: Mapped[Decimal | None] = mapped_column(Numeric)
    others: Mapped[Decimal | None] = mapped_column(Numeric)
    pay_all_tax: Mapped[Decimal | None] = mapped_column(Numeric)
    plus_assets_depre_prep: Mapped[Decimal | None] = mapped_column(Numeric)
    plus_end_bal_cash_equ: Mapped[Decimal | None] = mapped_column(Numeric)
    recp_tax_refund: Mapped[Decimal | None] = mapped_column(Numeric)
    use_right_asset_dep: Mapped[Decimal | None] = mapped_column(Numeric)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<CashFlow(symbol={self.symbol!r}"
            f", reporting_period={self.reporting_period!r}"
            f", statement_type={self.statement_type!r})>"
        )


class Income(Base):
    """表 "income"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "income"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    symbol: Mapped[str] = mapped_column(Text, primary_key=True)
    security_name: Mapped[str | None] = mapped_column(Text)
    statement_type: Mapped[str] = mapped_column(Text, primary_key=True)
    report_type: Mapped[str | None] = mapped_column(Text)
    reporting_period: Mapped[date] = mapped_column(Date, primary_key=True)
    ann_date: Mapped[date | None] = mapped_column(Date)
    actual_ann_date: Mapped[date | None] = mapped_column(Date)
    comp_type_code: Mapped[str | None] = mapped_column(Text)
    amort_cost_fin_assets_ear: Mapped[Decimal | None] = mapped_column(Numeric)
    basic_eps: Mapped[Decimal | None] = mapped_column(Numeric)
    beg_undistributed_pro: Mapped[Decimal | None] = mapped_column(Numeric)
    capitalized_com_stock_div: Mapped[Decimal | None] = mapped_column(Numeric)
    comments: Mapped[str | None] = mapped_column(Text)
    common_stock_div_payable: Mapped[Decimal | None] = mapped_column(Numeric)
    continued_net_opera_pro: Mapped[Decimal | None] = mapped_column(Numeric)
    credit_impair_loss: Mapped[Decimal | None] = mapped_column(Numeric)
    currency_code: Mapped[str | None] = mapped_column(Text)
    diluted_eps: Mapped[Decimal | None] = mapped_column(Numeric)
    distributive_pro: Mapped[Decimal | None] = mapped_column(Numeric)
    distributive_pro_shareholder: Mapped[Decimal | None] = mapped_column(Numeric)
    div_exp_insur: Mapped[Decimal | None] = mapped_column(Numeric)
    ebit: Mapped[Decimal | None] = mapped_column(Numeric)
    ebitda: Mapped[Decimal | None] = mapped_column(Numeric)
    employee_welfare: Mapped[Decimal | None] = mapped_column(Numeric)
    end_net_opera_pro: Mapped[Decimal | None] = mapped_column(Numeric)
    ext_insur_cont_rsrv: Mapped[Decimal | None] = mapped_column(Numeric)
    ext_unearned_prem_res: Mapped[Decimal | None] = mapped_column(Numeric)
    fin_exp_int_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    fin_exp_int_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    gain_disposal_assets: Mapped[Decimal | None] = mapped_column(Numeric)
    handling_chrg_comm_fee: Mapped[Decimal | None] = mapped_column(Numeric)
    incl_inc_inv_jv_entp: Mapped[Decimal | None] = mapped_column(Numeric)
    incl_less_loss_disp_ncur_asset: Mapped[Decimal | None] = mapped_column(Numeric)
    incl_reinsur_prem_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    income_tax: Mapped[Decimal | None] = mapped_column(Numeric)
    insur_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    insur_prem: Mapped[Decimal | None] = mapped_column(Numeric)
    interest_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    is_calculation: Mapped[Decimal | None] = mapped_column(Numeric)
    less_admin_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    less_amort_compen_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    less_amort_insur_cont_rsrv: Mapped[Decimal | None] = mapped_column(Numeric)
    less_amort_reinsur_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    less_assets_impair_loss: Mapped[Decimal | None] = mapped_column(Numeric)
    less_bus_tax_surcharge: Mapped[Decimal | None] = mapped_column(Numeric)
    less_fin_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    less_handling_chrg_comm_fee: Mapped[Decimal | None] = mapped_column(Numeric)
    less_interest_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    less_non_opera_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    less_opera_cost: Mapped[Decimal | None] = mapped_column(Numeric)
    less_reinsur_prem: Mapped[Decimal | None] = mapped_column(Numeric)
    less_selling_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    min_int_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    net_exposure_hedging_gain: Mapped[Decimal | None] = mapped_column(Numeric)
    net_handling_chrg_comm_fee: Mapped[Decimal | None] = mapped_column(Numeric)
    net_inc_ec_asset_mgmt_bus: Mapped[Decimal | None] = mapped_column(Numeric)
    net_inc_sec_brok_bus: Mapped[Decimal | None] = mapped_column(Numeric)
    net_inc_sec_uw_bus: Mapped[Decimal | None] = mapped_column(Numeric)
    net_interest_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    net_pro_after_ded_nr_gl: Mapped[Decimal | None] = mapped_column(Numeric)
    net_pro_after_ded_nr_gl_cor: Mapped[Decimal | None] = mapped_column(Numeric)
    net_pro_excl_min_int_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    net_pro_incl_min_int_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    net_pro_under_int_acc_sta: Mapped[Decimal | None] = mapped_column(Numeric)
    opera_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    opera_profit: Mapped[Decimal | None] = mapped_column(Numeric)
    opera_rev: Mapped[Decimal | None] = mapped_column(Numeric)
    oth_assets_impair_loss: Mapped[Decimal | None] = mapped_column(Numeric)
    oth_bus_cost: Mapped[Decimal | None] = mapped_column(Numeric)
    oth_bus_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    oth_compre_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    oth_income: Mapped[Decimal | None] = mapped_column(Numeric)
    oth_net_opera_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    plus_net_fx_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    plus_net_gain_chg_fv: Mapped[Decimal | None] = mapped_column(Numeric)
    plus_net_inv_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    plus_non_opera_rev: Mapped[Decimal | None] = mapped_column(Numeric)
    plus_oth_net_bus_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    preferred_share_div_payable: Mapped[Decimal | None] = mapped_column(Numeric)
    prem_bus_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    rd_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    reinsurance_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    spe_bal_net_pro_marg: Mapped[Decimal | None] = mapped_column(Numeric)
    spe_bal_opera_pro_marg: Mapped[Decimal | None] = mapped_column(Numeric)
    spe_bal_tot_opera_cost_dif: Mapped[Decimal | None] = mapped_column(Numeric)
    spe_bal_tot_opera_inc_dif: Mapped[Decimal | None] = mapped_column(Numeric)
    spe_bal_tot_pro_marg: Mapped[Decimal | None] = mapped_column(Numeric)
    spe_tot_opera_cost_dif_state: Mapped[Decimal | None] = mapped_column(Numeric)
    spe_tot_opera_inc_dif_state: Mapped[Decimal | None] = mapped_column(Numeric)
    surr_value: Mapped[Decimal | None] = mapped_column(Numeric)
    tot_bal_net_pro_marg: Mapped[Decimal | None] = mapped_column(Numeric)
    tot_bal_opera_pro_marg: Mapped[Decimal | None] = mapped_column(Numeric)
    tot_bal_tot_pro_marg: Mapped[Decimal | None] = mapped_column(Numeric)
    tot_compen_exp: Mapped[Decimal | None] = mapped_column(Numeric)
    tot_compre_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    tot_compre_inc_min_share: Mapped[Decimal | None] = mapped_column(Numeric)
    tot_compre_inc_parent_comp: Mapped[Decimal | None] = mapped_column(Numeric)
    tot_opera_cost: Mapped[Decimal | None] = mapped_column(Numeric)
    tot_opera_cost2: Mapped[Decimal | None] = mapped_column(Numeric)
    tot_opera_rev: Mapped[Decimal | None] = mapped_column(Numeric)
    total_profit: Mapped[Decimal | None] = mapped_column(Numeric)
    transfer_housing_revo_funds: Mapped[Decimal | None] = mapped_column(Numeric)
    transfer_others: Mapped[Decimal | None] = mapped_column(Numeric)
    transfer_surplus_reserve: Mapped[Decimal | None] = mapped_column(Numeric)
    unconfirmed_inv_loss: Mapped[Decimal | None] = mapped_column(Numeric)
    withdraw_any_surplus_resv: Mapped[Decimal | None] = mapped_column(Numeric)
    withdraw_ent_develop_fund: Mapped[Decimal | None] = mapped_column(Numeric)
    withdraw_leg_pub_wel_fund: Mapped[Decimal | None] = mapped_column(Numeric)
    withdraw_leg_surplus: Mapped[Decimal | None] = mapped_column(Numeric)
    withdraw_resv_fund: Mapped[Decimal | None] = mapped_column(Numeric)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<Income(symbol={self.symbol!r}"
            f", reporting_period={self.reporting_period!r}"
            f", statement_type={self.statement_type!r})>"
        )


class ProfitExpress(Base):
    """表 "profit_express"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "profit_express"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    symbol: Mapped[str] = mapped_column(Text, primary_key=True)
    reporting_period: Mapped[date] = mapped_column(Date, primary_key=True)
    ann_date: Mapped[date | None] = mapped_column(Date)
    actual_ann_date: Mapped[date | None] = mapped_column(Date)
    total_assets: Mapped[Decimal | None] = mapped_column(Numeric)
    net_pro_excl_min_int_inc: Mapped[Decimal | None] = mapped_column(Numeric)
    tot_opera_rev: Mapped[Decimal | None] = mapped_column(Numeric)
    total_profit: Mapped[Decimal | None] = mapped_column(Numeric)
    opera_profit: Mapped[Decimal | None] = mapped_column(Numeric)
    eps_basic: Mapped[Decimal | None] = mapped_column(Numeric)
    tot_share_equity_excl_min_int: Mapped[Decimal | None] = mapped_column(Numeric)
    is_audit: Mapped[bool | None] = mapped_column(Boolean)
    roe_weighted: Mapped[Decimal | None] = mapped_column(Numeric)
    last_year_revised_net_pro: Mapped[Decimal | None] = mapped_column(Numeric)
    performance_summary: Mapped[str | None] = mapped_column(Text)
    net_asset_ps: Mapped[Decimal | None] = mapped_column(Numeric)
    memo: Mapped[str | None] = mapped_column(Text)
    yoy_gr_gross_pro: Mapped[Decimal | None] = mapped_column(Numeric)
    yoy_gr_gross_rev: Mapped[Decimal | None] = mapped_column(Numeric)
    yoy_gr_net_profit_parent: Mapped[Decimal | None] = mapped_column(Numeric)
    yoy_gr_tot_pro: Mapped[Decimal | None] = mapped_column(Numeric)
    yoy_id_waroe: Mapped[Decimal | None] = mapped_column(Numeric)
    yoy_gr_eps_basic: Mapped[Decimal | None] = mapped_column(Numeric)
    growth_rate_equity: Mapped[Decimal | None] = mapped_column(Numeric)
    growth_rate_assets: Mapped[Decimal | None] = mapped_column(Numeric)
    growth_rate_naps: Mapped[Decimal | None] = mapped_column(Numeric)
    last_year_tot_opera_rev: Mapped[Decimal | None] = mapped_column(Numeric)
    last_year_total_profit: Mapped[Decimal | None] = mapped_column(Numeric)
    last_year_opera_pro: Mapped[Decimal | None] = mapped_column(Numeric)
    last_year_eps_diluted: Mapped[Decimal | None] = mapped_column(Numeric)
    last_year_net_profit: Mapped[Decimal | None] = mapped_column(Numeric)
    initial_net_asset_ps: Mapped[Decimal | None] = mapped_column(Numeric)
    initial_net_assets: Mapped[Decimal | None] = mapped_column(Numeric)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<ProfitExpress(symbol={self.symbol!r}, reporting_period={self.reporting_period!r})>"
        )


class ProfitNotice(Base):
    """表 "profit_notice"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "profit_notice"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    symbol: Mapped[str] = mapped_column(Text, primary_key=True)
    security_name: Mapped[str | None] = mapped_column(Text)
    reporting_period: Mapped[date] = mapped_column(Date, primary_key=True)
    ann_date: Mapped[date] = mapped_column(Date, primary_key=True)
    p_typecode: Mapped[str | None] = mapped_column(Text)
    report_type: Mapped[str | None] = mapped_column(Text)
    p_change_max: Mapped[Decimal | None] = mapped_column(Numeric)
    p_change_min: Mapped[Decimal | None] = mapped_column(Numeric)
    net_profit_max: Mapped[Decimal | None] = mapped_column(Numeric)
    net_profit_min: Mapped[Decimal | None] = mapped_column(Numeric)
    first_ann_date: Mapped[date | None] = mapped_column(Date)
    p_number: Mapped[int | None] = mapped_column(BigInteger)
    p_reason: Mapped[str | None] = mapped_column(Text)
    p_summary: Mapped[str | None] = mapped_column(Text)
    p_net_parent_firm: Mapped[Decimal | None] = mapped_column(Numeric)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<ProfitNotice(symbol={self.symbol!r}"
            f", reporting_period={self.reporting_period!r}"
            f", ann_date={self.ann_date!r})>"
        )


class Dividend(Base):
    """表 "dividend"(nocodb 形态,2026-08-26 回迁)."""

    __tablename__ = "dividend"

    id: Mapped[int | None] = mapped_column(Integer, comment="NocoDB 行 id(serial,应用不写)")
    symbol: Mapped[str] = mapped_column(Text, primary_key=True)
    reporting_period: Mapped[date] = mapped_column(Date, primary_key=True)
    ann_date: Mapped[date] = mapped_column(Date, primary_key=True)
    div_progress: Mapped[str | None] = mapped_column(Text)
    dvd_per_share_stk: Mapped[Decimal | None] = mapped_column(Numeric)
    dvd_per_share_pre_tax_cash: Mapped[Decimal | None] = mapped_column(Numeric)
    dvd_per_share_after_tax_cash: Mapped[Decimal | None] = mapped_column(Numeric)
    date_eqy_record: Mapped[date | None] = mapped_column(Date)
    date_ex: Mapped[date | None] = mapped_column(Date)
    date_dvd_payout: Mapped[date | None] = mapped_column(Date)
    listingdate_of_dvd_shr: Mapped[date | None] = mapped_column(Date)
    div_prelandate: Mapped[date | None] = mapped_column(Date)
    div_smtgdate: Mapped[date | None] = mapped_column(Date)
    date_dvd_ann: Mapped[date | None] = mapped_column(Date)
    div_basedate: Mapped[date | None] = mapped_column(Date)
    div_baseshare: Mapped[Decimal | None] = mapped_column(Numeric)
    currency_code: Mapped[str | None] = mapped_column(Text)
    is_changed: Mapped[bool | None] = mapped_column(Boolean)
    div_change: Mapped[str | None] = mapped_column(Text)
    div_bonusrate: Mapped[Decimal | None] = mapped_column(Numeric)
    div_conversedrate: Mapped[Decimal | None] = mapped_column(Numeric)
    remark: Mapped[str | None] = mapped_column(Text)
    div_preann_date: Mapped[date | None] = mapped_column(Date)
    div_target: Mapped[str | None] = mapped_column(Text)
    # 审计/系统列(应用不写;created_at/updated_at 由 DB DEFAULT 与 upsert set_ 维护)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<Dividend(symbol={self.symbol!r}"
            f", reporting_period={self.reporting_period!r}"
            f", ann_date={self.ann_date!r})>"
        )
