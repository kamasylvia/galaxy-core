"""财务数据 Provider Adapter 单元测试.

测试 InfoDataProviderAdapter 的 5 个接口方法以及枚举/值对象。
"""

import asyncio
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from galaxy_core.amazing_data.api.adapters.financial_data_provider_adapter import (
    InfoDataProviderAdapter,
)
from galaxy_core.amazing_data.api.client import AmazingDataClient
from galaxy_core.domain.ports.financial_data_provider import FinancialDataProviderPort
from galaxy_core.domain.value_objects import (
    FinancialDataType,
    FinancialRecord,
    FinancialSyncResult,
    ReportType,
)

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MagicMock:
    """返回 MagicMock(spec=AmazingDataClient)."""
    return MagicMock(spec=AmazingDataClient)


@pytest.fixture
def adapter(mock_client: MagicMock) -> InfoDataProviderAdapter:
    """返回配置好 mock client 的 InfoDataProviderAdapter."""
    return InfoDataProviderAdapter(mock_client)


def _make_balance_sheet_df() -> pd.DataFrame:
    """构造模拟 balance_sheet API 返回的 DataFrame."""
    return pd.DataFrame(
        {
            "MARKET_CODE": ["600000.SH"],
            "SECURITY_NAME": ["浦发银行"],
            "STATEMENT_TYPE": ["1"],
            "REPORT_TYPE": ["1"],
            "REPORTING_PERIOD": ["20240331"],
            "ANN_DATE": ["20240428"],
            "ACTUAL_ANN_DATE": ["20240428"],
            "COMP_TYPE_CODE": ["1"],
            "ACC_PAYABLE": [1.23e10],
            "ACC_RECEIVABLE": [4.56e9],
        },
    )


def _make_profit_express_df() -> pd.DataFrame:
    """构造模拟 profit_express API 返回的 DataFrame（非 dict 返回的情况也用 dict 包装测试）."""
    return pd.DataFrame(
        {
            "MARKET_CODE": ["600000.SH"],
            "SECURITY_NAME": ["浦发银行"],
            "REPORT_TYPE": ["1"],
            "REPORTING_PERIOD": ["20240331"],
            "ANN_DATE": ["20240420"],
            "ACTUAL_ANN_DATE": ["20240420"],
            "COMP_TYPE_CODE": ["1"],
            "YSHCSR": [5.0e9],
        },
    )


# ---------------------------------------------------------------------------
# Protocol 验证
# ---------------------------------------------------------------------------


class TestInfoDataProviderAdapterProtocol:
    """验证 InfoDataProviderAdapter 满足 FinancialDataProviderPort Protocol."""

    def test_adapter_is_protocol_instance(self, adapter: InfoDataProviderAdapter):
        """adapter 应满足 FinancialDataProviderPort Protocol."""
        assert isinstance(adapter, FinancialDataProviderPort)

    def test_adapter_has_async_get_balance_sheet(self, adapter: InfoDataProviderAdapter):
        """get_balance_sheet 应为 async 方法."""
        import inspect

        assert inspect.iscoroutinefunction(adapter.get_balance_sheet)

    def test_adapter_has_async_get_cash_flow(self, adapter: InfoDataProviderAdapter):
        """get_cash_flow 应为 async 方法."""
        import inspect

        assert inspect.iscoroutinefunction(adapter.get_cash_flow)

    def test_adapter_has_async_get_income_statement(self, adapter: InfoDataProviderAdapter):
        """get_income_statement 应为 async 方法."""
        import inspect

        assert inspect.iscoroutinefunction(adapter.get_income_statement)


# ---------------------------------------------------------------------------
# 三大报表成功测试
# ---------------------------------------------------------------------------


class TestGetBalanceSheetSuccess:
    """get_balance_sheet 成功场景."""

    def test_returns_financial_records(self, mock_client, adapter):
        """mock client 返回 DataFrame dict，验证返回 list[FinancialRecord] 且字段映射正确."""
        df = _make_balance_sheet_df()
        mock_client.get_balance_sheet.return_value = {"600000.SH": df}

        result = asyncio.run(adapter.get_balance_sheet(["600000.SH"], "20240101", "20240630"))

        assert len(result) == 1
        rec = result[0]
        assert isinstance(rec, FinancialRecord)
        assert rec.symbol == "600000.SH"
        assert rec.reporting_period == "20240331"
        assert rec.data_type == FinancialDataType.BALANCE_SHEET
        # 验证 snake_case 字段映射: ACC_PAYABLE -> acc_payable
        assert "acc_payable" in rec.fields
        assert rec.fields["acc_payable"] == pytest.approx(1.23e10)


class TestGetCashFlowSuccess:
    """get_cash_flow 成功场景."""

    def test_returns_financial_records(
        self, mock_client: MagicMock, adapter: InfoDataProviderAdapter
    ):
        df = pd.DataFrame(
            {
                "MARKET_CODE": ["000001.SZ"],
                "SECURITY_NAME": ["平安银行"],
                "STATEMENT_TYPE": ["1"],
                "REPORT_TYPE": ["2"],
                "REPORTING_PERIOD": ["20240630"],
                "ANN_DATE": ["20240815"],
                "ACTUAL_ANN_DATE": ["20240815"],
                "COMP_TYPE_CODE": ["1"],
                "CASH_END_BAL": [3.0e10],
            },
        )
        mock_client.get_cash_flow.return_value = {"000001.SZ": df}

        result = asyncio.run(adapter.get_cash_flow(["000001.SZ"], "20240101", "20241231"))

        assert len(result) == 1
        assert result[0].data_type == FinancialDataType.CASH_FLOW
        assert result[0].symbol == "000001.SZ"
        assert "cash_end_bal" in result[0].fields


class TestGetIncomeSuccess:
    """get_income_statement 成功场景."""

    def test_returns_financial_records(
        self, mock_client: MagicMock, adapter: InfoDataProviderAdapter
    ):
        df = pd.DataFrame(
            {
                "MARKET_CODE": ["600000.SH"],
                "SECURITY_NAME": ["浦发银行"],
                "STATEMENT_TYPE": ["1"],
                "REPORT_TYPE": ["3"],
                "REPORTING_PERIOD": ["20240930"],
                "ANN_DATE": ["20241030"],
                "ACTUAL_ANN_DATE": ["20241030"],
                "COMP_TYPE_CODE": ["1"],
                "TOTAL_OPERATE_INCOME": [2.0e10],
            },
        )
        mock_client.get_income_statement.return_value = {"600000.SH": df}

        result = asyncio.run(adapter.get_income_statement(["600000.SH"], "20240101", "20241231"))

        assert len(result) == 1
        assert result[0].data_type == FinancialDataType.INCOME
        assert "total_operate_income" in result[0].fields


# ---------------------------------------------------------------------------
# 业绩快报/预告成功测试
# ---------------------------------------------------------------------------


class TestGetProfitExpressSuccess:
    """get_profit_express 成功场景."""

    def test_returns_financial_records(
        self, mock_client: MagicMock, adapter: InfoDataProviderAdapter
    ):
        df = _make_profit_express_df()
        mock_client.get_profit_express.return_value = {"600000.SH": df}

        result = asyncio.run(adapter.get_profit_express(["600000.SH"], "20240101", "20241231"))

        assert len(result) == 1
        assert result[0].data_type == FinancialDataType.PROFIT_EXPRESS
        # 业绩快报无 statement_type
        assert result[0].statement_type is None


class TestGetProfitNoticeSuccess:
    """get_profit_notice 成功场景."""

    def test_returns_financial_records(
        self, mock_client: MagicMock, adapter: InfoDataProviderAdapter
    ):
        df = pd.DataFrame(
            {
                "MARKET_CODE": ["600000.SH"],
                "SECURITY_NAME": ["浦发银行"],
                "REPORT_TYPE": ["4"],
                "REPORTING_PERIOD": ["20241231"],
                "ANN_DATE": ["20250115"],
                "ACTUAL_ANN_DATE": ["20250120"],
                "COMP_TYPE_CODE": ["1"],
                "FORECAST_TYPE": ["预增"],
            },
        )
        mock_client.get_profit_notice.return_value = {"600000.SH": df}

        result = asyncio.run(adapter.get_profit_notice(["600000.SH"], "20240101", "20241231"))

        assert len(result) == 1
        assert result[0].data_type == FinancialDataType.PROFIT_NOTICE
        assert result[0].statement_type is None


class TestGetDividendSuccess:
    """get_dividend 成功场景."""

    def test_returns_financial_records(
        self, mock_client: MagicMock, adapter: InfoDataProviderAdapter
    ):
        df = pd.DataFrame(
            {
                "MARKET_CODE": ["600000.SH"],
                "SECURITY_NAME": ["浦发银行"],
                "REPORT_TYPE": ["1"],
                "REPORT_PERIOD": ["20241231"],
                "ANN_DATE": ["20250515"],
                "ACTUAL_ANN_DATE": ["20250515"],
                "COMP_TYPE_CODE": ["1"],
                "DVD_PER_SHARE_STK": [0.0],
                "DVD_PER_SHARE_PRE_TAX_CASH": [0.5],
                "DVD_PER_SHARE_AFTER_TAX_CASH": [0.4],
                "DIV_PROGRESS": ["3"],
            },
        )
        mock_client.get_dividend.return_value = {"600000.SH": df}

        result = asyncio.run(adapter.get_dividend(["600000.SH"], "20240101", "20251231"))

        assert len(result) == 1
        rec = result[0]
        assert rec.data_type == FinancialDataType.DIVIDEND
        assert rec.symbol == "600000.SH"
        assert rec.reporting_period == "20241231"
        assert rec.statement_type is None
        assert "dvd_per_share_pre_tax_cash" in rec.fields
        assert rec.fields["dvd_per_share_pre_tax_cash"] == pytest.approx(0.5)
        assert rec.fields["div_progress"] == "3"


# ---------------------------------------------------------------------------
# 空响应测试
# ---------------------------------------------------------------------------


class TestEmptyResponse:
    """空响应场景."""

    def test_empty_response_returns_empty_list(
        self, mock_client: MagicMock, adapter: InfoDataProviderAdapter
    ):
        """mock 返回空 DataFrame，验证返回 []."""
        mock_client.get_balance_sheet.return_value = {"600000.SH": pd.DataFrame()}

        result = asyncio.run(adapter.get_balance_sheet(["600000.SH"], "20240101", "20240630"))

        assert result == []

    def test_none_response_returns_empty_list(
        self, mock_client: MagicMock, adapter: InfoDataProviderAdapter
    ):
        """mock 返回 None DataFrame，验证跳过."""
        mock_client.get_balance_sheet.return_value = {"600000.SH": None}

        result = asyncio.run(adapter.get_balance_sheet(["600000.SH"], "20240101", "20240630"))

        assert result == []

    def test_empty_dict_returns_empty_list(
        self, mock_client: MagicMock, adapter: InfoDataProviderAdapter
    ):
        """mock 返回 {}，验证返回 []."""
        mock_client.get_balance_sheet.return_value = {}

        result = asyncio.run(adapter.get_balance_sheet(["600000.SH"], "20240101", "20240630"))

        assert result == []


# ---------------------------------------------------------------------------
# asyncio.to_thread 验证
# ---------------------------------------------------------------------------


class TestAsyncioToThread:
    """验证所有方法内部调用 asyncio.to_thread."""

    def test_to_thread_used_in_get_balance_sheet(self, adapter: InfoDataProviderAdapter):
        async def run():
            with patch(
                "galaxy_core.amazing_data.api.adapters.financial_data_provider_adapter.asyncio.to_thread"
            ) as mock_to_thread:
                mock_to_thread.return_value = {}
                result = await adapter.get_balance_sheet(["600000.SH"], "20240101", "20240630")
                mock_to_thread.assert_called_once()
                return result

        asyncio.run(run())

    def test_to_thread_used_in_get_cash_flow(self, adapter: InfoDataProviderAdapter):
        async def run():
            with patch(
                "galaxy_core.amazing_data.api.adapters.financial_data_provider_adapter.asyncio.to_thread"
            ) as mock_to_thread:
                mock_to_thread.return_value = {}
                result = await adapter.get_cash_flow(["600000.SH"], "20240101", "20240630")
                mock_to_thread.assert_called_once()
                return result

        asyncio.run(run())

    def test_to_thread_used_in_get_income_statement(self, adapter: InfoDataProviderAdapter):
        async def run():
            with patch(
                "galaxy_core.amazing_data.api.adapters.financial_data_provider_adapter.asyncio.to_thread"
            ) as mock_to_thread:
                mock_to_thread.return_value = {}
                result = await adapter.get_income_statement(["600000.SH"], "20240101", "20240630")
                mock_to_thread.assert_called_once()
                return result

        asyncio.run(run())

    def test_to_thread_used_in_get_profit_express(self, adapter: InfoDataProviderAdapter):
        async def run():
            with patch(
                "galaxy_core.amazing_data.api.adapters.financial_data_provider_adapter.asyncio.to_thread"
            ) as mock_to_thread:
                mock_to_thread.return_value = {}
                result = await adapter.get_profit_express(["600000.SH"], "20240101", "20240630")
                mock_to_thread.assert_called_once()
                return result

        asyncio.run(run())

    def test_to_thread_used_in_get_profit_notice(self, adapter: InfoDataProviderAdapter):
        async def run():
            with patch(
                "galaxy_core.amazing_data.api.adapters.financial_data_provider_adapter.asyncio.to_thread"
            ) as mock_to_thread:
                mock_to_thread.return_value = {}
                result = await adapter.get_profit_notice(["600000.SH"], "20240101", "20240630")
                mock_to_thread.assert_called_once()
                return result

        asyncio.run(run())

    def test_to_thread_used_in_get_dividend(self, adapter: InfoDataProviderAdapter):
        async def run():
            with patch(
                "galaxy_core.amazing_data.api.adapters.financial_data_provider_adapter.asyncio.to_thread"
            ) as mock_to_thread:
                mock_to_thread.return_value = {}
                result = await adapter.get_dividend(["600000.SH"], "20240101", "20251231")
                mock_to_thread.assert_called_once()
                return result

        asyncio.run(run())


# ---------------------------------------------------------------------------
# 枚举与值对象测试
# ---------------------------------------------------------------------------


class TestFinancialDataTypeEnum:
    """FinancialDataType 枚举值验证."""

    def test_financial_data_type_values(self):
        """验证 6 个枚举值正确."""
        assert FinancialDataType.BALANCE_SHEET == "balance_sheet"
        assert FinancialDataType.CASH_FLOW == "cash_flow"
        assert FinancialDataType.INCOME == "income"
        assert FinancialDataType.PROFIT_EXPRESS == "profit_express"
        assert FinancialDataType.PROFIT_NOTICE == "profit_notice"
        assert FinancialDataType.DIVIDEND == "dividend"
        assert len(FinancialDataType) == 6


class TestReportTypeEnum:
    """ReportType 枚举值验证."""

    def test_report_type_values(self):
        """验证 Q1=1, H1=2, Q3=3, ANNUAL=4."""
        assert ReportType.Q1 == 1
        assert ReportType.H1 == 2
        assert ReportType.Q3 == 3
        assert ReportType.ANNUAL == 4
        assert len(ReportType) == 4


class TestFinancialRecordCreation:
    """FinancialRecord 实例化测试."""

    def test_financial_record_creation(self):
        """验证 FinancialRecord 可正确实例化."""
        rec = FinancialRecord(
            symbol="600000.SH",
            reporting_period="20240331",
            statement_type="1",
            ann_date="20240428",
            actual_ann_date="20240428",
            data_type=FinancialDataType.BALANCE_SHEET,
            fields={"acc_payable": 1.23e10},
        )
        assert rec.symbol == "600000.SH"
        assert rec.reporting_period == "20240331"
        assert rec.statement_type == "1"
        assert rec.actual_ann_date == "20240428"
        assert rec.data_type == FinancialDataType.BALANCE_SHEET
        assert rec.fields["acc_payable"] == pytest.approx(1.23e10)


class TestFinancialSyncResultDefaults:
    """FinancialSyncResult 默认值测试."""

    def test_financial_sync_result_defaults(self):
        """验证 FinancialSyncResult 默认值为 0/[]."""
        result = FinancialSyncResult()
        assert result.total_symbols == 0
        assert result.success_count == 0
        assert result.synced_records == 0
        assert result.failed_codes == []
