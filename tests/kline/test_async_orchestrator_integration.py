"""Integration tests for async orchestrator.

Tests verify execute_kline_query_async uses AsyncKlineService correctly
and async database operations don't block the event loop.
"""

import asyncio
import sys
import time
import types
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

# Mock AmazingData SDK before importing galaxy_db_sync
if "AmazingData" not in sys.modules:
    sys.modules["AmazingData"] = types.SimpleNamespace(
        login=lambda **kwargs: None,
        logout=lambda *args, **kwargs: None,
        BaseData=lambda: types.SimpleNamespace(get_calendar=lambda *args, **kwargs: []),
        InfoData=lambda: types.SimpleNamespace(),
        MarketData=lambda calendar: types.SimpleNamespace(query_kline=lambda **kwargs: {}),
    )

if "akshare" not in sys.modules:
    sys.modules["akshare"] = types.SimpleNamespace()

if "tgw" not in sys.modules:
    sys.modules["tgw"] = types.SimpleNamespace()

from galaxy_db_sync.application.kline.sync_orchestrator import (
    execute_kline_query_async,
    group_symbols_by_missing_ranges,
)
from galaxy_db_sync.database.core.async_connection import AsyncDatabaseManager
from galaxy_db_sync.database.services.kline_completeness_checker import (
    CompletenessResult,
)


@pytest.fixture
def mock_async_db_manager() -> AsyncMock:
    """Create a mock AsyncDatabaseManager."""
    manager = AsyncMock(spec=AsyncDatabaseManager)
    manager.session = MagicMock()
    return manager


@pytest.fixture
def sample_kline_data() -> pd.DataFrame:
    """Create sample K-line data."""
    return pd.DataFrame(
        {
            "trade_time": [datetime(2023, 1, 1), datetime(2023, 1, 2)],
            "open": [10.0, 11.0],
            "high": [10.5, 11.5],
            "low": [9.5, 10.5],
            "close": [10.2, 11.2],
            "volume": [1000, 1100],
            "amount": [10000, 11000],
        }
    ).set_index("trade_time")


class TestAsyncOrchestratorIntegration:
    """Integration tests for async orchestrator flow."""

    @pytest.mark.asyncio
    async def test_execute_kline_query_async_uses_async_db(self, mock_async_db_manager, sample_kline_data):
        """Test execute_kline_query_async creates AsyncKlineService internally."""
        expected_db_data = {"600000.SH": sample_kline_data}

        with (
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.AsyncKlineService"
            ) as mock_service_class,
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.kline_completeness_checker.check"
            ) as mock_check,
        ):
            # Setup AsyncKlineService mock
            mock_service = AsyncMock()
            mock_service.query_kline_from_db = AsyncMock(return_value=expected_db_data)
            mock_service.merge_db_and_api_data = MagicMock(return_value=expected_db_data)
            mock_service_class.return_value = mock_service

            # Setup completeness check to return complete (no API fetch needed)
            mock_check.return_value = CompletenessResult(
                is_complete=True,
                missing_count=0,
                total_count=10,
                coverage_ratio=1.0,
                missing_ranges=[],
                check_method="short_period_trading_day",
            )

            result = await execute_kline_query_async(
                symbol_list=["600000.SH"],
                interval="day",
                start_date="20230101",
                end_date="20231231",
                interval_value=10008,
                async_db_manager=mock_async_db_manager,
            )

        assert "600000.SH" in result
        mock_service_class.assert_called_once_with(mock_async_db_manager)
        mock_service.query_kline_from_db.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_kline_query_async_with_incomplete_data_triggers_api_fetch(
        self, mock_async_db_manager, sample_kline_data
    ):
        """Test full flow: DB query + API fetch + merge with mocks."""
        db_data = {"600000.SH": sample_kline_data.iloc[:1]}  # Partial DB data
        api_data = {"600000.SH": sample_kline_data.iloc[1:]}  # API fills the gap
        merged_data = {"600000.SH": sample_kline_data}

        with (
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.AsyncKlineService"
            ) as mock_service_class,
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.kline_completeness_checker.check"
            ) as mock_check,
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.empty_query_service.is_confirmed_empty",
                return_value=False,
            ),
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.batch_fetch_kline_data",
                return_value=(api_data, []),
            ) as mock_batch_fetch,
        ):
            # Setup AsyncKlineService mock
            mock_service = AsyncMock()
            mock_service.query_kline_from_db = AsyncMock(return_value=db_data)
            mock_service.merge_db_and_api_data = MagicMock(return_value=merged_data)
            mock_service_class.return_value = mock_service

            # Setup completeness check to return incomplete
            mock_check.return_value = CompletenessResult(
                is_complete=False,
                missing_count=1,
                total_count=2,
                coverage_ratio=0.5,
                missing_ranges=[(datetime(2023, 1, 2), datetime(2023, 1, 2))],
                check_method="short_period_trading_day",
            )

            result = await execute_kline_query_async(
                symbol_list=["600000.SH"],
                interval="day",
                start_date="20230101",
                end_date="20231231",
                interval_value=10008,
                async_db_manager=mock_async_db_manager,
            )

        assert "600000.SH" in result
        # Verify async DB query was called
        mock_service.query_kline_from_db.assert_awaited_once()
        # Verify API fetch was triggered (via asyncio.to_thread)
        mock_batch_fetch.assert_called_once()
        # Verify merge was called
        mock_service.merge_db_and_api_data.assert_called_once_with(db_data, api_data)

    @pytest.mark.asyncio
    async def test_execute_kline_query_async_with_failed_api_codes(
        self, mock_async_db_manager, sample_kline_data
    ):
        """Test handling of failed API codes during fetch."""
        db_data = {"600000.SH": sample_kline_data}
        api_data = {}  # Empty API data
        failed_codes = ["600001.SH"]  # Failed symbol
        merged_data = {"600000.SH": sample_kline_data}

        with (
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.AsyncKlineService"
            ) as mock_service_class,
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.kline_completeness_checker.check"
            ) as mock_check,
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.empty_query_service.is_confirmed_empty",
                return_value=False,
            ),
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.batch_fetch_kline_data",
                return_value=(api_data, failed_codes),
            ),
        ):
            mock_service = AsyncMock()
            mock_service.query_kline_from_db = AsyncMock(return_value=db_data)
            mock_service.merge_db_and_api_data = MagicMock(return_value=merged_data)
            mock_service_class.return_value = mock_service

            mock_check.return_value = CompletenessResult(
                is_complete=False,
                missing_count=1,
                total_count=2,
                coverage_ratio=0.5,
                missing_ranges=[(datetime(2023, 1, 1), datetime(2023, 1, 2))],
                check_method="short_period_trading_day",
            )

            result = await execute_kline_query_async(
                symbol_list=["600000.SH"],
                interval="day",
                start_date="20230101",
                end_date="20231231",
                interval_value=10008,
                async_db_manager=mock_async_db_manager,
            )

        # Should still return merged data even with failed codes
        assert "600000.SH" in result
        mock_service.merge_db_and_api_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_db_does_not_block_event_loop(self, mock_async_db_manager):
        """Verify async DB operations don't block concurrent tasks.

        This test demonstrates that multiple execute_kline_query_async calls
        can run concurrently without blocking each other.
        """
        import time

        async def slow_db_query(*args, **kwargs):
            await asyncio.sleep(0.05)  # Simulate async DB delay
            return {"600000.SH": pd.DataFrame()}

        with (
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.AsyncKlineService"
            ) as mock_service_class,
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.kline_completeness_checker.check"
            ) as mock_check,
        ):
            mock_service = AsyncMock()
            mock_service.query_kline_from_db = AsyncMock(side_effect=slow_db_query)
            mock_service.merge_db_and_api_data = MagicMock(
                return_value={"600000.SH": pd.DataFrame()}
            )
            mock_service_class.return_value = mock_service

            mock_check.return_value = CompletenessResult(
                is_complete=True,
                missing_count=0,
                total_count=1,
                coverage_ratio=1.0,
                missing_ranges=[],
                check_method="short_period_trading_day",
            )

            start = time.time()
            # Run two queries concurrently
            results = await asyncio.gather(
                execute_kline_query_async(
                    symbol_list=["600000.SH"],
                    interval="day",
                    start_date="20230101",
                    end_date="20230131",
                    interval_value=10008,
                    async_db_manager=mock_async_db_manager,
                ),
                execute_kline_query_async(
                    symbol_list=["600001.SH"],
                    interval="day",
                    start_date="20230101",
                    end_date="20230131",
                    interval_value=10008,
                    async_db_manager=mock_async_db_manager,
                ),
            )
            elapsed = time.time() - start

        assert len(results) == 2
        # Should complete in ~0.05s (concurrent), not ~0.1s (sequential)
        assert elapsed < 0.10, f"Queries took {elapsed:.3f}s - event loop was blocked"

    @pytest.mark.asyncio
    async def test_group_symbols_by_missing_ranges_excludes_confirmed_empty(self):
        """Test that confirmed empty queries are excluded from range groups."""
        completeness_results = {
            "600000.SH": CompletenessResult(
                is_complete=False,
                missing_count=1,
                total_count=2,
                coverage_ratio=0.5,
                missing_ranges=[(datetime(2023, 1, 1), datetime(2023, 1, 2))],
                check_method="short_period_trading_day",
            ),
            "600001.SH": CompletenessResult(
                is_complete=False,
                missing_count=1,
                total_count=2,
                coverage_ratio=0.5,
                missing_ranges=[(datetime(2023, 1, 1), datetime(2023, 1, 2))],
                check_method="short_period_trading_day",
            ),
        }

        with patch(
            "galaxy_db_sync.application.kline.sync_orchestrator.empty_query_service.is_confirmed_empty"
        ) as mock_is_empty:
            # 600000.SH has confirmed empty, 600001.SH does not
            mock_is_empty.side_effect = lambda symbol, interval, start, end: symbol == "600000.SH"

            range_groups = group_symbols_by_missing_ranges(
                completeness_results,
                "day",
                10008,
            )

        # Only 600001.SH should be in range groups
        all_symbols_in_groups = []
        for symbols in range_groups.values():
            all_symbols_in_groups.extend(symbols)

        assert "600000.SH" not in all_symbols_in_groups
        assert "600001.SH" in all_symbols_in_groups

    @pytest.mark.asyncio
    async def test_execute_kline_query_async_uses_default_db_manager_when_none_provided(self, sample_kline_data):
        """Test that default async_db_manager is used when None is provided."""
        expected_db_data = {"600000.SH": sample_kline_data}

        with (
            patch(
                "galaxy_db_sync.database.core.async_connection.async_db_manager"
            ) as mock_default_manager,
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.AsyncKlineService"
            ) as mock_service_class,
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.kline_completeness_checker.check"
            ) as mock_check,
        ):
            mock_service = AsyncMock()
            mock_service.query_kline_from_db = AsyncMock(return_value=expected_db_data)
            mock_service.merge_db_and_api_data = MagicMock(return_value=expected_db_data)
            mock_service_class.return_value = mock_service

            mock_check.return_value = CompletenessResult(
                is_complete=True,
                missing_count=0,
                total_count=10,
                coverage_ratio=1.0,
                missing_ranges=[],
                check_method="short_period_trading_day",
            )

            result = await execute_kline_query_async(
                symbol_list=["600000.SH"],
                interval="day",
                start_date="20230101",
                end_date="20231231",
                interval_value=10008,
                async_db_manager=None,  # Explicitly None
            )

        assert "600000.SH" in result
        # Should have used the default manager
        mock_service_class.assert_called_once_with(mock_default_manager)


class TestAsyncOrchestratorEdgeCases:
    """Edge case tests for async orchestrator."""

    @pytest.mark.asyncio
    async def test_empty_symbol_list_returns_empty_dict(self, mock_async_db_manager):
        """Test that empty symbol list returns empty dictionary."""
        with patch(
            "galaxy_db_sync.application.kline.sync_orchestrator.AsyncKlineService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.query_kline_from_db = AsyncMock(return_value={})
            mock_service.merge_db_and_api_data = MagicMock(return_value={})
            mock_service_class.return_value = mock_service

            result = await execute_kline_query_async(
                symbol_list=[],  # Empty list
                interval="day",
                start_date="20230101",
                end_date="20231231",
                interval_value=10008,
                async_db_manager=mock_async_db_manager,
            )

        assert result == {}

    @pytest.mark.asyncio
    async def test_multiple_intervals_in_same_call(self, mock_async_db_manager, sample_kline_data):
        """Test handling multiple symbols with different completeness results."""
        expected_db_data = {
            "600000.SH": sample_kline_data,
            "600001.SH": sample_kline_data,
        }

        with (
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.AsyncKlineService"
            ) as mock_service_class,
            patch(
                "galaxy_db_sync.application.kline.sync_orchestrator.kline_completeness_checker.check"
            ) as mock_check,
        ):
            mock_service = AsyncMock()
            mock_service.query_kline_from_db = AsyncMock(return_value=expected_db_data)
            mock_service.merge_db_and_api_data = MagicMock(return_value=expected_db_data)
            mock_service_class.return_value = mock_service

            # All symbols complete
            mock_check.return_value = CompletenessResult(
                is_complete=True,
                missing_count=0,
                total_count=10,
                coverage_ratio=1.0,
                missing_ranges=[],
                check_method="short_period_trading_day",
            )

            result = await execute_kline_query_async(
                symbol_list=["600000.SH", "600001.SH"],
                interval="day",
                start_date="20230101",
                end_date="20231231",
                interval_value=10008,
                async_db_manager=mock_async_db_manager,
            )

        assert len(result) == 2
        assert "600000.SH" in result
        assert "600001.SH" in result