"""财务数据 Service 层单元测试.

测试 FinancialDataService 的 sync 流程和辅助函数。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from galaxy_core.domain.value_objects import (
    FinancialDataType,
    FinancialRecord,
    FinancialSyncResult,
)
from galaxy_core.services.financial_data_service import (
    FinancialDataService,
    _last_reporting_period,
    _next_period,
    _prev_n_years,
)

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_provider():
    """mock FinancialDataProviderPort."""
    provider = MagicMock()
    provider.get_balance_sheet = AsyncMock(return_value=[])
    provider.get_cash_flow = AsyncMock(return_value=[])
    provider.get_income_statement = AsyncMock(return_value=[])
    provider.get_profit_express = AsyncMock(return_value=[])
    provider.get_profit_notice = AsyncMock(return_value=[])
    return provider


@pytest.fixture
def mock_store():
    """mock FinancialDataStorePort."""
    store = MagicMock()
    store.save = AsyncMock()
    store.get_last_sync_periods = AsyncMock(return_value={})
    store.set_last_sync_periods = AsyncMock()
    return store


@pytest.fixture
def mock_reference_provider():
    """mock ReferenceProviderPort."""
    ref = MagicMock()
    ref.get_stock_list = AsyncMock(return_value=["600000.SH", "000001.SZ"])
    ref.get_hist_code_list = AsyncMock(return_value=["600000.SH", "000001.SZ"])
    ref.get_listing_dates = AsyncMock(
        return_value={"600000.SH": "20200101", "000001.SZ": "20200101"}
    )
    return ref


@pytest.fixture
def service(mock_provider, mock_store, mock_reference_provider):
    """返回配置好 mock 依赖的 FinancialDataService."""
    return FinancialDataService(mock_provider, mock_store, mock_reference_provider)


def _make_record(symbol="600000.SH", period="20240331") -> FinancialRecord:
    """构造测试用 FinancialRecord."""
    return FinancialRecord(
        symbol=symbol,
        reporting_period=period,
        statement_type="1",
        ann_date="20240428",
        actual_ann_date="20240428",
        data_type=FinancialDataType.BALANCE_SHEET,
        fields={"acc_payable": 1.23e10},
    )


# ---------------------------------------------------------------------------
# 辅助函数测试
# ---------------------------------------------------------------------------


class TestNextPeriod:
    """_next_period 辅助函数测试."""

    def test_q1_to_h1(self):
        assert _next_period("20240331") == "20240630"

    def test_h1_to_q3(self):
        assert _next_period("20240630") == "20240930"

    def test_q3_to_annual(self):
        assert _next_period("20240930") == "20241231"

    def test_annual_to_next_year_q1(self):
        assert _next_period("20241231") == "20250331"

    def test_invalid_period_raises(self):
        with pytest.raises(ValueError, match="非法季度末日期"):
            _next_period("20240101")


class TestPrevNYears:
    """_prev_n_years 辅助函数测试."""

    def test_3_years_back(self):
        assert _prev_n_years("20240331", 3) == "20210331"

    def test_1_year_back(self):
        assert _prev_n_years("20241231", 1) == "20231231"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="非法日期格式"):
            _prev_n_years("202401", 3)


class TestLastReportingPeriod:
    """_last_reporting_period 辅助函数测试."""

    def test_returns_valid_format(self):
        result = _last_reporting_period()
        assert len(result) == 8
        assert result[4:] in ("0331", "0630", "0930", "1231")


# ---------------------------------------------------------------------------
# 增量同步测试
# ---------------------------------------------------------------------------


class TestSyncIncremental:
    """增量同步测试."""

    @pytest.mark.asyncio
    async def test_sync_incremental(self, service, mock_provider, mock_store):
        """mock provider 返回 2 条记录，验证增量同步调用路径."""
        records = [_make_record("600000.SH"), _make_record("000001.SZ")]
        mock_provider.get_balance_sheet = AsyncMock(return_value=records)
        # 有 last_sync_period 的 symbol 会从 next_period 开始
        mock_store.get_last_sync_periods = AsyncMock(return_value={"600000.SH": "20231231"})

        result = await service.sync(
            data_type=FinancialDataType.BALANCE_SHEET,
            symbols=["600000.SH", "000001.SZ"],
            start="20240101",
            end="20240630",
        )

        assert isinstance(result, FinancialSyncResult)
        assert result.synced_records == 2
        mock_store.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_with_explicit_symbols(
        self, service, mock_provider, mock_reference_provider
    ):
        """传入 symbols 列表，验证直接使用（不调用 reference_provider.get_stock_list）."""
        mock_provider.get_balance_sheet = AsyncMock(return_value=[])

        await service.sync(
            data_type=FinancialDataType.BALANCE_SHEET,
            symbols=["600000.SH"],
            start="20240101",
            end="20240630",
        )

        mock_reference_provider.get_stock_list.assert_not_called()
        mock_reference_provider.get_hist_code_list.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_without_symbols(self, service, mock_provider, mock_reference_provider):
        """symbols=None，验证调用 reference_provider.get_stock_list."""
        mock_provider.get_balance_sheet = AsyncMock(return_value=[])

        await service.sync(
            data_type=FinancialDataType.BALANCE_SHEET,
            symbols=None,
            start="20240101",
            end="20240630",
        )

        mock_reference_provider.get_hist_code_list.assert_called_once()


# ---------------------------------------------------------------------------
# 全量刷新测试
# ---------------------------------------------------------------------------


class TestSyncFullRefresh:
    """全量刷新测试."""

    @pytest.mark.asyncio
    async def test_sync_full_refresh(self, service, mock_provider):
        """full_refresh=True，验证查询 3 年范围."""
        mock_provider.get_balance_sheet = AsyncMock(return_value=[])

        await service.sync(
            data_type=FinancialDataType.BALANCE_SHEET,
            symbols=["600000.SH"],
            full_refresh=True,
            end="20240331",
        )

        # full_refresh 应调用 provider 以 _prev_n_years(end, 3) 为起始
        call_args = mock_provider.get_balance_sheet.call_args
        assert call_args is not None
        # begin_date 应为 20210331（3 年前）
        assert call_args.kwargs["begin_date"] == "20210331"
        assert call_args.kwargs["end_date"] == "20240331"


# ---------------------------------------------------------------------------
# 空响应测试
# ---------------------------------------------------------------------------


class TestSyncEmptyResponse:
    """空 API 响应测试."""

    @pytest.mark.asyncio
    async def test_sync_empty_api_response(self, service, mock_provider, mock_store):
        """mock 返回空列表，验证 last_sync_period 不推进."""
        mock_provider.get_balance_sheet = AsyncMock(return_value=[])

        result = await service.sync(
            data_type=FinancialDataType.BALANCE_SHEET,
            symbols=["600000.SH"],
            start="20240101",
            end="20240630",
        )

        # 无记录时 set_last_sync_periods 不应被调用
        mock_store.set_last_sync_periods.assert_not_called()
        assert result.synced_records == 0


# ---------------------------------------------------------------------------
# 同步结果统计测试
# ---------------------------------------------------------------------------


class TestSyncResultCounts:
    """FinancialSyncResult 统计测试."""

    @pytest.mark.asyncio
    async def test_sync_result_counts(self, service, mock_provider):
        """验证 FinancialSyncResult 统计正确."""
        records = [_make_record("600000.SH"), _make_record("000001.SZ")]
        mock_provider.get_balance_sheet = AsyncMock(return_value=records)

        result = await service.sync(
            data_type=FinancialDataType.BALANCE_SHEET,
            symbols=["600000.SH", "000001.SZ"],
            start="20240101",
            end="20240630",
        )

        assert result.total_symbols == 2
        assert result.success_count == 2
        assert result.synced_records == 2
        assert result.failed_codes == []


# ---------------------------------------------------------------------------
# _compute_symbol_max_periods 测试
# ---------------------------------------------------------------------------


class TestComputeSymbolMaxPeriods:
    """_compute_symbol_max_periods 静态方法测试."""

    def test_returns_max_period_per_symbol(self):
        records = [
            _make_record("600000.SH", "20240331"),
            _make_record("600000.SH", "20240630"),
            _make_record("000001.SZ", "20240331"),
        ]
        result = FinancialDataService._compute_symbol_max_periods(records)
        assert result == {"600000.SH": "20240630", "000001.SZ": "20240331"}

    def test_empty_records_returns_empty(self):
        result = FinancialDataService._compute_symbol_max_periods([])
        assert result == {}


# ---------------------------------------------------------------------------
# _filter_active 测试
# ---------------------------------------------------------------------------


class TestFilterActive:
    """_filter_active 方法测试."""

    @pytest.mark.asyncio
    async def test_filters_delisted(self, service, mock_reference_provider):
        """无上市日期的 symbol 应被过滤."""
        mock_reference_provider.get_listing_dates = AsyncMock(
            return_value={"600000.SH": "20200101", "000001.SZ": None}
        )

        result = await service._filter_active(["600000.SH", "000001.SZ"])
        assert result == ["600000.SH"]

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self, service):
        result = await service._filter_active([])
        assert result == []
