"""财务数据 CLI 命令单元测试.

测试 handle_financial_command_async 的参数解析和服务调用。
"""

import argparse
from unittest.mock import AsyncMock, MagicMock

import pytest

from galaxy_core.application.financial.command import handle_financial_command_async
from galaxy_core.domain.value_objects import (
    FinancialDataType,
    FinancialSyncResult,
)

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_financial_service():
    """mock FinancialDataService."""
    service = MagicMock()
    service.sync = AsyncMock(
        return_value=FinancialSyncResult(
            total_symbols=1,
            success_count=1,
            synced_records=5,
            failed_codes=[],
        )
    )
    return service


def _make_args(**overrides) -> argparse.Namespace:
    """构造 CLI 参数 Namespace."""
    defaults = {
        "type": "balance_sheet",
        "symbol": None,
        "start": None,
        "end": None,
        "full_refresh": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# CLI 命令测试
# ---------------------------------------------------------------------------


class TestHandleFinancialCommand:
    """handle_financial_command_async 测试."""

    @pytest.mark.asyncio
    async def test_handle_financial_command_basic(self, mock_financial_service):
        """基本调用：type="balance_sheet"，验证调用 financial_service.sync."""
        args = _make_args(type="balance_sheet")

        result = await handle_financial_command_async(args, mock_financial_service)

        assert result == 0
        mock_financial_service.sync.assert_called_once()
        call_kwargs = mock_financial_service.sync.call_args.kwargs
        assert call_kwargs["data_type"] == FinancialDataType.BALANCE_SHEET
        assert call_kwargs["symbols"] is None
        assert call_kwargs["full_refresh"] is False

    @pytest.mark.asyncio
    async def test_handle_financial_command_with_symbol(self, mock_financial_service):
        """args 含 symbol，验证传入 symbols=["600000.SH"]."""
        args = _make_args(symbol="600000.SH")

        result = await handle_financial_command_async(args, mock_financial_service)

        assert result == 0
        call_kwargs = mock_financial_service.sync.call_args.kwargs
        assert call_kwargs["symbols"] == ["600000.SH"]

    @pytest.mark.asyncio
    async def test_handle_financial_command_with_date_range(self, mock_financial_service):
        """args 含 start/end，验证传入日期."""
        args = _make_args(start="20230101", end="20241231")

        result = await handle_financial_command_async(args, mock_financial_service)

        assert result == 0
        call_kwargs = mock_financial_service.sync.call_args.kwargs
        assert call_kwargs["start"] == "20230101"
        assert call_kwargs["end"] == "20241231"

    @pytest.mark.asyncio
    async def test_handle_financial_command_full_refresh(self, mock_financial_service):
        """args.full_refresh=True，验证传入."""
        args = _make_args(full_refresh=True)

        result = await handle_financial_command_async(args, mock_financial_service)

        assert result == 0
        call_kwargs = mock_financial_service.sync.call_args.kwargs
        assert call_kwargs["full_refresh"] is True

    @pytest.mark.asyncio
    async def test_handle_financial_command_invalid_type(self):
        """不支持的 data_type 应返回 1."""
        args = _make_args(type="invalid_type")
        mock_service = MagicMock()

        result = await handle_financial_command_async(args, mock_service)

        assert result == 1
        mock_service.sync.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_financial_command_no_service(self):
        """financial_service=None 应返回 1."""
        args = _make_args()

        result = await handle_financial_command_async(args, None)

        assert result == 1

    @pytest.mark.asyncio
    async def test_handle_all_data_types(self, mock_financial_service):
        """验证所有 6 种 data_type 都能正确解析."""
        type_names = [
            "balance_sheet",
            "cash_flow",
            "income",
            "profit_express",
            "profit_notice",
            "dividend",
        ]
        expected_types = [
            FinancialDataType.BALANCE_SHEET,
            FinancialDataType.CASH_FLOW,
            FinancialDataType.INCOME,
            FinancialDataType.PROFIT_EXPRESS,
            FinancialDataType.PROFIT_NOTICE,
            FinancialDataType.DIVIDEND,
        ]

        for type_name, expected in zip(type_names, expected_types, strict=True):
            mock_financial_service.sync.reset_mock()
            args = _make_args(type=type_name)

            result = await handle_financial_command_async(args, mock_financial_service)

            assert result == 0
            call_kwargs = mock_financial_service.sync.call_args.kwargs
            assert call_kwargs["data_type"] == expected
