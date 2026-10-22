"""财务数据 Store Adapter 单元测试.

测试 FinancialDataStoreAdapter 的 save / get_last_sync_periods / set_last_sync_periods。
"""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from galaxy_core.database.services.adapters.financial_data_store_adapter import (
    FinancialDataStoreAdapter,
)
from galaxy_core.domain.ports.financial_data_store import FinancialDataStorePort
from galaxy_core.domain.value_objects import FinancialDataType, FinancialRecord

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


def _make_mock_session():
    """构造 mock AsyncSession context manager."""
    mock_session = AsyncMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_session, mock_session_ctx


@pytest.fixture
def mock_db_manager():
    """提供 async context manager mock 的 db_manager."""
    mock_session, mock_session_ctx = _make_mock_session()
    mock_db = MagicMock()
    mock_db.session.return_value = mock_session_ctx
    return mock_db, mock_session


@pytest.fixture
def adapter(mock_db_manager):
    """返回配置好 mock db_manager 的 FinancialDataStoreAdapter."""
    mock_db, _ = mock_db_manager
    return FinancialDataStoreAdapter(mock_db)


def _make_balance_sheet_record(symbol="600000.SH") -> FinancialRecord:
    """构造一条 balance_sheet FinancialRecord."""
    return FinancialRecord(
        symbol=symbol,
        reporting_period="20240331",
        statement_type="1",
        ann_date="20240428",
        actual_ann_date="20240428",
        data_type=FinancialDataType.BALANCE_SHEET,
        fields={"acc_payable": 1.23e10, "acc_receivable": 4.56e9},
    )


def _make_cash_flow_record(symbol="000001.SZ") -> FinancialRecord:
    """构造一条 cash_flow FinancialRecord."""
    return FinancialRecord(
        symbol=symbol,
        reporting_period="20240630",
        statement_type="1",
        ann_date="20240815",
        actual_ann_date="20240815",
        data_type=FinancialDataType.CASH_FLOW,
        fields={"cash_end_bal": 3.0e10},
    )


def _make_income_record(symbol="600000.SH") -> FinancialRecord:
    """构造一条 income FinancialRecord."""
    return FinancialRecord(
        symbol=symbol,
        reporting_period="20240930",
        statement_type="1",
        ann_date="20241030",
        actual_ann_date="20241030",
        data_type=FinancialDataType.INCOME,
        fields={"total_operate_income": 2.0e10},
    )


def _make_profit_express_record(symbol="600000.SH") -> FinancialRecord:
    """构造一条 profit_express FinancialRecord."""
    return FinancialRecord(
        symbol=symbol,
        reporting_period="20240331",
        statement_type=None,
        ann_date="20240420",
        actual_ann_date="20240420",
        data_type=FinancialDataType.PROFIT_EXPRESS,
        fields={"yshcsr": 5.0e9},
    )


def _make_profit_notice_record(symbol="600000.SH") -> FinancialRecord:
    """构造一条 profit_notice FinancialRecord."""
    return FinancialRecord(
        symbol=symbol,
        reporting_period="20241231",
        statement_type=None,
        ann_date="20250120",
        actual_ann_date="20250120",
        data_type=FinancialDataType.PROFIT_NOTICE,
        fields={"forecast_type": "预增"},
    )


def _make_dividend_record(symbol="600000.SH") -> FinancialRecord:
    """构造一条 dividend FinancialRecord."""
    return FinancialRecord(
        symbol=symbol,
        reporting_period="20241231",
        statement_type=None,
        ann_date="20250515",
        actual_ann_date="20250515",
        data_type=FinancialDataType.DIVIDEND,
        fields={
            "div_progress": "3",
            "dvd_per_share_pre_tax_cash": 0.5,
            "dvd_per_share_after_tax_cash": 0.4,
        },
    )


# ---------------------------------------------------------------------------
# Protocol 验证
# ---------------------------------------------------------------------------


class TestFinancialDataStoreAdapterProtocol:
    """验证 FinancialDataStoreAdapter 满足 FinancialDataStorePort Protocol."""

    def test_adapter_is_protocol_instance(self, adapter: FinancialDataStoreAdapter):
        """FinancialDataStoreAdapter 应满足 FinancialDataStorePort Protocol."""
        assert isinstance(adapter, FinancialDataStorePort)

    def test_adapter_has_async_save(self, adapter: FinancialDataStoreAdapter):
        """save 应为 async 方法."""
        import inspect

        assert inspect.iscoroutinefunction(adapter.save)

    def test_adapter_has_async_get_last_sync_periods(self, adapter: FinancialDataStoreAdapter):
        """get_last_sync_periods 应为 async 方法."""
        import inspect

        assert inspect.iscoroutinefunction(adapter.get_last_sync_periods)

    def test_adapter_has_async_set_last_sync_periods(self, adapter: FinancialDataStoreAdapter):
        """set_last_sync_periods 应为 async 方法."""
        import inspect

        assert inspect.iscoroutinefunction(adapter.set_last_sync_periods)


# ---------------------------------------------------------------------------
# 5 张表保存测试
# ---------------------------------------------------------------------------


class TestSaveBalanceSheet:
    """save balance_sheet 测试."""

    def test_save_balance_sheet(self, mock_db_manager):
        """验证 balance_sheet 保存时 session.execute 被调用."""
        mock_db, mock_session = mock_db_manager
        adapter = FinancialDataStoreAdapter(mock_db)

        records = [_make_balance_sheet_record()]
        asyncio.run(adapter.save(records, FinancialDataType.BALANCE_SHEET))

        mock_db.session.assert_called_once()
        mock_session.execute.assert_called()


class TestSaveCashFlow:
    """save cash_flow 测试."""

    def test_save_cash_flow(self, mock_db_manager):
        mock_db, mock_session = mock_db_manager
        adapter = FinancialDataStoreAdapter(mock_db)

        records = [_make_cash_flow_record()]
        asyncio.run(adapter.save(records, FinancialDataType.CASH_FLOW))

        mock_db.session.assert_called_once()
        mock_session.execute.assert_called()


class TestSaveIncome:
    """save income 测试."""

    def test_save_income(self, mock_db_manager):
        mock_db, mock_session = mock_db_manager
        adapter = FinancialDataStoreAdapter(mock_db)

        records = [_make_income_record()]
        asyncio.run(adapter.save(records, FinancialDataType.INCOME))

        mock_db.session.assert_called_once()
        mock_session.execute.assert_called()


class TestSaveProfitExpress:
    """save profit_express 测试 — PK 为 (symbol, reporting_period)."""

    def test_save_profit_express(self, mock_db_manager):
        mock_db, mock_session = mock_db_manager
        adapter = FinancialDataStoreAdapter(mock_db)

        records = [_make_profit_express_record()]
        asyncio.run(adapter.save(records, FinancialDataType.PROFIT_EXPRESS))

        mock_db.session.assert_called_once()
        mock_session.execute.assert_called()


class TestSaveProfitNotice:
    """save profit_notice 测试 — PK 为 (symbol, reporting_period)."""

    def test_save_profit_notice(self, mock_db_manager):
        mock_db, mock_session = mock_db_manager
        adapter = FinancialDataStoreAdapter(mock_db)

        records = [_make_profit_notice_record()]
        asyncio.run(adapter.save(records, FinancialDataType.PROFIT_NOTICE))

        mock_db.session.assert_called_once()
        mock_session.execute.assert_called()


class TestSaveDividend:
    """save dividend 测试 — PK 为 (symbol, reporting_period, ann_date)."""

    def test_save_dividend(self, mock_db_manager):
        mock_db, mock_session = mock_db_manager
        adapter = FinancialDataStoreAdapter(mock_db)

        records = [_make_dividend_record()]
        asyncio.run(adapter.save(records, FinancialDataType.DIVIDEND))

        mock_db.session.assert_called_once()
        mock_session.execute.assert_called()


# ---------------------------------------------------------------------------
# 空记录测试
# ---------------------------------------------------------------------------


class TestSaveEmptyRecords:
    """空记录测试."""

    def test_save_empty_records(self, mock_db_manager):
        """传入空列表，验证不执行 SQL."""
        mock_db, mock_session = mock_db_manager
        adapter = FinancialDataStoreAdapter(mock_db)

        asyncio.run(adapter.save([], FinancialDataType.BALANCE_SHEET))

        mock_db.session.assert_not_called()
        mock_session.execute.assert_not_called()


# ---------------------------------------------------------------------------
# last_sync_period 读写测试
# ---------------------------------------------------------------------------


class TestGetLastSyncPeriods:
    """get_last_sync_periods 测试."""

    def test_returns_periods_dict(self, mock_db_manager):
        """验证返回 MAX(reporting_period) 字典格式正确."""
        mock_db, mock_session = mock_db_manager
        adapter = FinancialDataStoreAdapter(mock_db)

        # 模拟数据库返回
        mock_row1 = MagicMock()
        mock_row1.symbol = "600000.SH"
        mock_row1.last_sync_date = date(2024, 3, 31)

        mock_row2 = MagicMock()
        mock_row2.symbol = "000001.SZ"
        mock_row2.last_sync_date = date(2024, 6, 30)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_row1, mock_row2]
        mock_session.execute.return_value = mock_result

        result = asyncio.run(
            adapter.get_last_sync_periods(
                ["600000.SH", "000001.SZ"], FinancialDataType.BALANCE_SHEET
            )
        )

        assert result == {
            "600000.SH": "20240331",
            "000001.SZ": "20240630",
        }

    def test_empty_symbols_returns_empty(self, mock_db_manager):
        """空 symbol 列表应直接返回 {}，不查询数据库."""
        mock_db, mock_session = mock_db_manager
        adapter = FinancialDataStoreAdapter(mock_db)

        result = asyncio.run(adapter.get_last_sync_periods([], FinancialDataType.BALANCE_SHEET))

        assert result == {}
        mock_db.session.assert_not_called()


class TestSetLastSyncPeriods:
    """set_last_sync_periods 测试."""

    def test_set_last_sync_periods(self, mock_db_manager):
        """验证 upsert 到 last_sync_date 表."""
        mock_db, mock_session = mock_db_manager
        adapter = FinancialDataStoreAdapter(mock_db)

        asyncio.run(
            adapter.set_last_sync_periods(
                {"600000.SH": "20240331"}, FinancialDataType.BALANCE_SHEET
            )
        )

        mock_db.session.assert_called_once()
        mock_session.execute.assert_called_once()

    def test_set_empty_dict_no_op(self, mock_db_manager):
        """空 dict 应直接返回，不操作数据库."""
        mock_db, mock_session = mock_db_manager
        adapter = FinancialDataStoreAdapter(mock_db)

        asyncio.run(adapter.set_last_sync_periods({}, FinancialDataType.BALANCE_SHEET))

        mock_db.session.assert_not_called()
