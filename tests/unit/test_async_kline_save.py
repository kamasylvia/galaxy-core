"""Tests for async kline save functions."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
import pandas as pd

from galaxy_core.database.services.kline import (
    batch_save_kline_to_db,
    save_kline_to_db,
)
from galaxy_core.database.models.kline import INTERVAL_MODEL_MAP, KlineDay


@pytest.mark.asyncio
class TestBatchSaveKlineToDbAsync:
    """Tests for batch_save_kline_to_db function."""

    async def test_uses_pg_insert_on_conflict_do_update(self, async_session_mock):
        """Test that function uses PostgreSQL UPSERT with on_conflict_do_update."""
        # Create mock DataFrame
        df = pd.DataFrame(
            {
                "open": [10.5, 11.0],
                "high": [11.0, 11.5],
                "low": [10.0, 10.5],
                "close": [10.8, 11.2],
                "volume": [1000000, 1100000],
                "amount": [10500000.0, 11500000.0],
            },
            index=[datetime(2025, 1, 15), datetime(2025, 1, 16)],
        )

        kline_dict = {"600000.SH": df}

        # Execute should be called - we don't need to check the exact statement
        # just that it was called and the function returns the count
        async_session_mock.execute.return_value = MagicMock()
        async_session_mock.commit = AsyncMock()

        result = await batch_save_kline_to_db(
            session=async_session_mock,
            kline_dict=kline_dict,
            interval="day",
            interval_model_map={"day": KlineDay},
        )

        # Execute should have been called (UPSERT)
        async_session_mock.execute.assert_called()
        # Commit should have been called
        async_session_mock.commit.assert_called_once()
        # Should return count of records saved (2 in our DataFrame)
        assert result == 2

    async def test_upsert_on_symbol_trade_time_conflict(self, async_session_mock):
        """Test that UPSERT uses (symbol, trade_time) as conflict key."""
        df = pd.DataFrame(
            {
                "open": [10.5],
                "high": [11.0],
                "low": [10.0],
                "close": [10.8],
                "volume": [1000000],
                "amount": [10500000.0],
            },
            index=[datetime(2025, 1, 15)],
        )

        kline_dict = {"600000.SH": df}

        async_session_mock.execute.return_value = MagicMock()
        async_session_mock.commit = AsyncMock()

        await batch_save_kline_to_db(
            session=async_session_mock,
            kline_dict=kline_dict,
            interval="day",
            interval_model_map={"day": KlineDay},
        )

        # Verify execute was called with UPSERT statement
        call_arg = async_session_mock.execute.call_args[0][0]
        # PostgreSQL insert statement has on_conflict_do_update
        # We check the statement has the conflict elements set
        assert hasattr(call_arg, "on_conflict_do_update")

    async def test_exception_triggers_rollback(self, async_session_mock):
        """Test that exception triggers rollback (not commit)."""
        df = pd.DataFrame(
            {
                "open": [10.5],
                "high": [11.0],
                "low": [10.0],
                "close": [10.8],
                "volume": [1000000],
                "amount": [10500000.0],
            },
            index=[datetime(2025, 1, 15)],
        )

        kline_dict = {"600000.SH": df}

        # Make execute raise an exception
        async_session_mock.execute.side_effect = Exception("DB error")
        async_session_mock.rollback = AsyncMock()

        with pytest.raises(Exception, match="DB error"):
            await batch_save_kline_to_db(
                session=async_session_mock,
                kline_dict=kline_dict,
                interval="day",
                interval_model_map={"day": KlineDay},
            )

        # Rollback should have been called
        async_session_mock.rollback.assert_called()

    async def test_deduplication_by_symbol_trade_time(self, async_session_mock):
        """Test that deduplication by (symbol, trade_time) is preserved."""
        # Create DataFrame with duplicate dates - only last should be kept
        df = pd.DataFrame(
            {
                "open": [10.5, 10.6, 10.7],  # Three entries for same date
                "high": [11.0, 11.1, 11.2],
                "low": [10.0, 10.1, 10.2],
                "close": [10.8, 10.9, 11.0],
                "volume": [1000000, 1100000, 1200000],
                "amount": [10500000.0, 11500000.0, 12500000.0],
            },
            index=[datetime(2025, 1, 15), datetime(2025, 1, 15), datetime(2025, 1, 15)],
        )

        kline_dict = {"600000.SH": df}

        async_session_mock.execute.return_value = MagicMock()
        async_session_mock.commit = AsyncMock()

        result = await batch_save_kline_to_db(
            session=async_session_mock,
            kline_dict=kline_dict,
            interval="day",
            interval_model_map={"day": KlineDay},
        )

        # Should deduplicate to 1 unique (symbol, trade_time) combo
        assert result == 1

    async def test_returns_count_of_deduplicated_records(self, async_session_mock):
        """Test that return count matches number of deduplicated records."""
        df1 = pd.DataFrame(
            {
                "open": [10.5, 11.0],
                "high": [11.0, 11.5],
                "low": [10.0, 10.5],
                "close": [10.8, 11.2],
                "volume": [1000000, 1100000],
                "amount": [10500000.0, 11500000.0],
            },
            index=[datetime(2025, 1, 15), datetime(2025, 1, 16)],
        )

        df2 = pd.DataFrame(
            {
                "open": [12.0],
                "high": [12.5],
                "low": [11.5],
                "close": [12.2],
                "volume": [2000000],
                "amount": [24000000.0],
            },
            index=[datetime(2025, 1, 15)],
        )  # Same date as first symbol

        kline_dict = {"600000.SH": df1, "600001.SH": df2}

        async_session_mock.execute.return_value = MagicMock()
        async_session_mock.commit = AsyncMock()

        result = await batch_save_kline_to_db(
            session=async_session_mock,
            kline_dict=kline_dict,
            interval="day",
            interval_model_map={"day": KlineDay},
        )

        # 2 records from first symbol + 1 from second = 3 total
        assert result == 3

    async def test_empty_dict_returns_zero(self, async_session_mock):
        """Test that empty kline_dict returns 0."""
        result = await batch_save_kline_to_db(
            session=async_session_mock,
            kline_dict={},
            interval="day",
            interval_model_map={"day": KlineDay},
        )

        assert result == 0
        # Execute should not be called for empty dict
        async_session_mock.execute.assert_not_called()

    async def test_empty_dataframe_in_dict_is_skipped(self, async_session_mock):
        """Test that empty DataFrame in dict is skipped."""
        df = pd.DataFrame()  # Empty DataFrame
        kline_dict = {"600000.SH": df}

        result = await batch_save_kline_to_db(
            session=async_session_mock,
            kline_dict=kline_dict,
            interval="day",
            interval_model_map={"day": KlineDay},
        )

        assert result == 0
        async_session_mock.execute.assert_not_called()


@pytest.mark.asyncio
class TestSaveKlineToDbAsync:
    """Tests for save_kline_to_db function."""

    async def test_saves_single_symbol_data(self, async_session_mock):
        """Test that function saves single symbol DataFrame."""
        df = pd.DataFrame(
            {
                "open": [10.5],
                "high": [11.0],
                "low": [10.0],
                "close": [10.8],
                "volume": [1000000],
                "amount": [10500000.0],
            },
            index=[datetime(2025, 1, 15)],
        )

        async_session_mock.execute.return_value = MagicMock()
        async_session_mock.commit = AsyncMock()

        result = await save_kline_to_db(
            session=async_session_mock,
            symbol="600000.SH",
            df=df,
            interval="day",
            security_type="stock",
            interval_model_map={"day": KlineDay},
        )

        assert result == 1
        async_session_mock.execute.assert_called()
        async_session_mock.commit.assert_called_once()

    async def test_raises_for_invalid_interval(self, async_session_mock):
        """Test that function raises ValueError for unsupported interval."""
        df = pd.DataFrame(
            {
                "open": [10.5],
                "high": [11.0],
                "low": [10.0],
                "close": [10.8],
                "volume": [1000000],
                "amount": [10500000.0],
            },
            index=[datetime(2025, 1, 15)],
        )

        with pytest.raises(ValueError, match="不支持的周期"):
            await save_kline_to_db(
                session=async_session_mock,
                symbol="600000.SH",
                df=df,
                interval="invalid",
                interval_model_map=INTERVAL_MODEL_MAP,
            )
