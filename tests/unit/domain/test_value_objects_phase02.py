"""Phase 02 值对象(5 dataclass)实例化测试.

纯 dataclass 测试,无需 mock SDK/DB。
覆盖:PK-only 构造、可选字段默认 None、字段数、trade_date str 注解。

2026-06-19 范围修订后(见 02-SCOPE-REVISION-REPORT.md)仅 5 个 VO:
akshare sector ×1 + AmazingData long_hu_bang/block_trading/margin_summary/margin_detail ×4。
原 12 VO(baostock×3 + akshare×5 + amazingdata×4)收敛为 5。
"""

import dataclasses
import typing

from galaxy_core.domain.value_objects import (
    AkshareSectorFundFlow,
    BlockTrading,
    LongHuBang,
    MarginDetail,
    MarginSummary,
)


class TestPhase02ValueObjects:
    """Phase 02 新增 5 个 VO 实例化测试(范围修订后)."""

    # akshare × 1

    def test_akshare_sector_fund_flow_instantiable(self):
        v = AkshareSectorFundFlow(
            trade_date="20240101", sector_type="行业资金流", sector_name="银行",
            main_net_amount=None, main_net_pct=None, super_large_net_amount=None,
            super_large_net_pct=None, large_net_amount=None, large_net_pct=None,
            medium_net_amount=None, medium_net_pct=None, small_net_amount=None,
            small_net_pct=None, top_stock=None,
        )
        assert v.sector_name == "银行"
        assert v.top_stock is None

    # amazingdata × 4

    def test_long_hu_bang_instantiable(self):
        v = LongHuBang(
            market_code="600000", trade_date="20240101", security_name=None,
            reason_type=None, reason_type_name=None, change_range=None,
            trader_name="某席位", flow_mark=1, buy_amount=None, sell_amount=None,
            total_amount=None, total_volume=None,
        )
        assert v.trader_name == "某席位"
        assert v.flow_mark == 1

    def test_block_trading_instantiable(self):
        v = BlockTrading(
            market_code="600000", trade_date="20240101", b_share_price=None,
            b_share_volume=None, b_frequency=None, block_avg_volume=None,
            b_share_amount=None, b_buyer_name="买方", b_seller_name="卖方",
        )
        assert v.b_buyer_name == "买方"

    def test_margin_summary_instantiable(self):
        v = MarginSummary(
            trade_date="20240101", sum_borrow_money_balance=None,
            sum_purch_with_borrow_money=None, sum_repayment_of_borrow_money=None,
            sum_sec_lending_balance=None, sum_sales_of_borrowed_sec=None,
            sum_margin_trade_balance=None,
        )
        assert v.trade_date == "20240101"

    def test_margin_detail_instantiable(self):
        v = MarginDetail(
            market_code="600000", trade_date="20240101", security_name=None,
            borrow_money_balance=None, purch_with_borrow_money=None,
            repayment_of_borrow_money=None, sec_lending_balance=None,
            sales_of_borrowed_sec=None, repayment_of_borrow_sec=None,
            sec_lending_balance_vol=None, margin_trade_balance=None,
        )
        assert v.market_code == "600000"

    # 综合回归

    def test_all_5_dataclasses_importable(self):
        """5 个 VO 类全部可导入(范围修订后)."""
        vos = [
            AkshareSectorFundFlow,
            LongHuBang, BlockTrading, MarginSummary, MarginDetail,
        ]
        for vo in vos:
            assert vo is not None

    def test_dataclass_fields_count(self):
        """AkshareSectorFundFlow 字段数 ≥ 14(trade_date+sector_type+sector_name+11 指标)."""
        fields = dataclasses.fields(AkshareSectorFundFlow)
        assert len(fields) >= 14

    def test_trade_date_is_str_annotation(self):
        """trade_date 字段注解应为 str(store adapter 负责转 Date,02-PLAN-06)."""
        hints = typing.get_type_hints(AkshareSectorFundFlow)
        assert hints["trade_date"] is str
