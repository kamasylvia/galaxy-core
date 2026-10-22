"""FundFlowStoreAdapter 单元测试.

mock _upsert 验证 4 save 方法 + 4 列 PK(long_hu_bang / block_trading)+
2 列 PK(margin_detail)+ 1 列 PK(margin_summary)。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from galaxy_core.database.services.adapters.fund_flow_store_adapter import (
    FundFlowStoreAdapter,
)
from galaxy_core.domain.value_objects import (
    BlockTrading,
    LongHuBang,
    MarginDetail,
    MarginSummary,
)


def _patch_upsert(adapter):
    mock = AsyncMock(return_value=1)
    patch.object(adapter, "_upsert", new=mock).start()
    return mock


@pytest.fixture
def adapter():
    return FundFlowStoreAdapter(MagicMock())


class TestFundFlowStoreAdapter:
    def test_save_long_hu_bang_4col_conflict(self, adapter):
        """关键:long_hu_bang 4 列 PK (market_code, trade_date, trader_name, flow_mark)."""
        records = [
            LongHuBang(
                market_code="600000.SH", trade_date="20260115", security_name=None,
                reason_type=None, reason_type_name=None, change_range=None,
                trader_name="某席位", flow_mark=1, buy_amount=None, sell_amount=None,
                total_amount=None, total_volume=None,
            )
        ]
        mock_upsert = _patch_upsert(adapter)
        asyncio.run(adapter.save_long_hu_bang(records))
        args = mock_upsert.call_args
        assert args.args[1] == ["market_code", "trade_date", "trader_name", "flow_mark"]

    def test_save_block_trading_4col_conflict(self, adapter):
        """关键:block_trading 4 列 PK (market_code, trade_date, b_buyer_name, b_seller_name)."""
        records = [
            BlockTrading(
                market_code="600000.SH", trade_date="20260115", b_share_price=None,
                b_share_volume=None, b_frequency=None, block_avg_volume=None,
                b_share_amount=None, b_buyer_name="买方", b_seller_name="卖方",
            )
        ]
        mock_upsert = _patch_upsert(adapter)
        asyncio.run(adapter.save_block_trading(records))
        args = mock_upsert.call_args
        assert args.args[1] == [
            "market_code", "trade_date", "b_buyer_name", "b_seller_name"
        ]

    def test_save_margin_summary_1col_conflict(self, adapter):
        records = [
            MarginSummary(
                trade_date="20260115", sum_borrow_money_balance=None,
                sum_purch_with_borrow_money=None, sum_repayment_of_borrow_money=None,
                sum_sec_lending_balance=None, sum_sales_of_borrowed_sec=None,
                sum_margin_trade_balance=None,
            )
        ]
        mock_upsert = _patch_upsert(adapter)
        asyncio.run(adapter.save_margin_summary(records))
        args = mock_upsert.call_args
        assert args.args[1] == ["trade_date"]

    def test_save_margin_detail_2col_conflict(self, adapter):
        records = [
            MarginDetail(
                market_code="600000.SH", trade_date="20260115", security_name=None,
                borrow_money_balance=None, purch_with_borrow_money=None,
                repayment_of_borrow_money=None, sec_lending_balance=None,
                sales_of_borrowed_sec=None, repayment_of_borrow_sec=None,
                sec_lending_balance_vol=None, margin_trade_balance=None,
            )
        ]
        mock_upsert = _patch_upsert(adapter)
        asyncio.run(adapter.save_margin_detail(records))
        args = mock_upsert.call_args
        assert args.args[1] == ["market_code", "trade_date"]

    def test_save_empty_returns_zero(self, adapter):
        assert asyncio.run(adapter.save_long_hu_bang([])) == 0
        assert asyncio.run(adapter.save_block_trading([])) == 0
        assert asyncio.run(adapter.save_margin_summary([])) == 0
        assert asyncio.run(adapter.save_margin_detail([])) == 0

    def test_4_save_methods_present(self, adapter):
        for m in [
            "save_long_hu_bang",
            "save_block_trading",
            "save_margin_summary",
            "save_margin_detail",
        ]:
            assert hasattr(adapter, m), f"missing {m}"

    def test_upsert_empty_data_returns_zero(self, adapter):
        from galaxy_core.database.models.fund_flow_data import LongHuBang
        result = asyncio.run(adapter._upsert(LongHuBang, ["market_code"], []))
        assert result == 0
