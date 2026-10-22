"""AkshareStoreAdapter 单元测试.

2026-06-19 范围修订后(见 02-SCOPE-REVISION-REPORT.md)仅 1 save 方法:
save_sector_fund_flow(sector 3 列 conflict)。原 5 save 收敛为 1。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from galaxy_core.database.services.adapters.akshare_store_adapter import (
    AkshareStoreAdapter,
)
from galaxy_core.domain.value_objects import AkshareSectorFundFlow


def _patch_upsert(adapter):
    """patch _upsert 为 AsyncMock,返 mock."""
    mock = AsyncMock(return_value=1)
    patch.object(adapter, "_upsert", new=mock).start()
    return mock


@pytest.fixture
def adapter():
    return AkshareStoreAdapter(MagicMock())


class TestAkshareStoreAdapter:
    def test_save_sector_fund_flow_3col_conflict(self, adapter):
        """关键:sector 3 列 PK (trade_date, sector_type, sector_name)."""
        records = [
            AkshareSectorFundFlow(
                trade_date="20260115", sector_type="行业资金流", sector_name="银行",
                main_net_amount=None, main_net_pct=None, super_large_net_amount=None,
                super_large_net_pct=None, large_net_amount=None, large_net_pct=None,
                medium_net_amount=None, medium_net_pct=None, small_net_amount=None,
                small_net_pct=None, top_stock=None,
            )
        ]
        mock_upsert = _patch_upsert(adapter)
        asyncio.run(adapter.save_sector_fund_flow(records))
        args = mock_upsert.call_args
        assert args.args[1] == ["trade_date", "sector_type", "sector_name"]

    def test_save_empty_returns_zero(self, adapter):
        assert asyncio.run(adapter.save_sector_fund_flow([])) == 0

    def test_save_method_present(self, adapter):
        assert hasattr(adapter, "save_sector_fund_flow"), "missing save_sector_fund_flow"

    def test_convert_trade_date_skips_invalid(self, adapter):
        """_convert_trade_date 跳过无效 trade_date 行."""
        data = [
            {"trade_date": "20260115", "symbol": "x"},
            {"trade_date": "bad", "symbol": "y"},
        ]
        result = AkshareStoreAdapter._convert_trade_date(data)
        assert len(result) == 1
        assert result[0]["symbol"] == "x"
