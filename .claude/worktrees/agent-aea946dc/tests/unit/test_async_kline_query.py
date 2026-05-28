"""Tests for async kline query functions."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
import pandas as pd

from galaxy_db_sync.database.services.kline import (
    query_kline_from_db,
    get_available_intervals_for_symbol,
    get_data_range_for_symbol,
)
from galaxy_db_sync.database.models.kline import INTERVAL_MODEL_MAP, KlineDay


@pytest.mark.asyncio
class TestQueryKlineFromDbAsync:
    """Tests for query_kline_from_db function."""

    async def test_returns_dataframe_dict_with_correct_format(self, async_session_mock):
        """Test that query returns Dict[str, pd.DataFrame] with expected format."""
        # Mock a KlineDay record
        mock_record = MagicMock()
        mock_record.symbol = "600000.SH"
        mock_record.trade_time = datetime(2025, 1, 15)
        mock_record.open = 10.5
        mock_record.high = 11.0
        mock_record.low = 10.0
        mock_record.close = 10.8
        mock_record.volume = 1000000
        mock_record.amount = 10500000.0

        # Mock the result chain: execute -> result -> scalars -> all
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_record]
        mock_result.scalars.return_value = mock_scalars
        async_session_mock.execute.return_value = mock_result

        result = await query_kline_from_db(
            session=async_session_mock,
            symbols=["600000.SH"],
            start_date="20250101",
            end_date="20250131",
            interval="day",
            interval_model_map=INTERVAL_MODEL_MAP,
        )

        assert "600000.SH" in result
        df = result["600000.SH"]
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["open", "high", "low", "close", "volume", "amount"]
        assert df.loc[datetime(2025, 1, 15)]["close"] == 10.8

    async def test_empty_result_returns_dataframe_with_correct_columns(self, async_session_mock):
        """Test that empty result returns DataFrame with correct columns for requested symbols."""
        # Mock empty result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        async_session_mock.execute.return_value = mock_result

        result = await query_kline_from_db(
            session=async_session_mock,
            symbols=["600000.SH", "600001.SH"],
            interval="day",
            interval_model_map=INTERVAL_MODEL_MAP,
        )

        # Both symbols should be in result, even if empty
        assert "600000.SH" in result
        assert "600001.SH" in result

        # Empty DataFrame should have correct columns and types
        for symbol in ["600000.SH", "600001.SH"]:
            df = result[symbol]
            assert df.empty
            assert list(df.columns) == ["open", "high", "low", "close", "volume", "amount"]

    async def test_query_uses_select_pattern_compatible_with_async(self, async_session_mock):
        """Test that query uses select() pattern that's async compatible."""
        # Mock records
        mock_record = MagicMock()
        mock_record.symbol = "600000.SH"
        mock_record.trade_time = datetime(2025, 1, 15)
        mock_record.open = 10.5
        mock_record.high = 11.0
        mock_record.low = 10.0
        mock_record.close = 10.8
        mock_record.volume = 1000000
        mock_record.amount = 10500000.0

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_record]
        mock_result.scalars.return_value = mock_scalars
        async_session_mock.execute.return_value = mock_result

        await query_kline_from_db(
            session=async_session_mock,
            symbols=["600000.SH"],
            interval="day",
            interval_model_map=INTERVAL_MODEL_MAP,
        )

        # Verify execute was called with a select statement (not legacy query)
        async_session_mock.execute.assert_called_once()
        call_arg = async_session_mock.execute.call_args[0][0]
        # The argument should be a SQLAlchemy Select object
        assert hasattr(call_arg, "where")

    async def test_date_parsing_for_month_interval(self, async_session_mock):
        """Test that date parsing works for month interval (boundary logic preserved)."""
        mock_record = MagicMock()
        mock_record.symbol = "600000.SH"
        mock_record.trade_time = datetime(2025, 1, 31)  # End of month
        mock_record.open = 10.5
        mock_record.high = 11.0
        mock_record.low = 10.0
        mock_record.close = 10.8
        mock_record.volume = 1000000
        mock_record.amount = 10500000.0

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_record]
        mock_result.scalars.return_value = mock_scalars
        async_session_mock.execute.return_value = mock_result

        result = await query_kline_from_db(
            session=async_session_mock,
            symbols=["600000.SH"],
            start_date="202501",  # Month format
            end_date="202501",
            interval="month",
            interval_model_map=INTERVAL_MODEL_MAP,
        )

        assert "600000.SH" in result
        # execute should have been called with parsed dates
        async_session_mock.execute.assert_called_once()


@pytest.mark.asyncio
class TestGetAvailableIntervalsForSymbolAsync:
    """Tests for get_available_intervals_for_symbol function."""

    async def test_returns_list_of_available_intervals(self, async_session_mock):
        """Test that function returns list of intervals with data."""
        # Mock count results - day interval has data, min1 does not
        mock_day_result = MagicMock()
        mock_day_result.scalar.return_value = 100  # Has data

        mock_min1_result = MagicMock()
        mock_min1_result.scalar.return_value = 0  # No data

        # Set up execute to return different results based on query
        call_count = 0

        def mock_execute_side_effect(query):
            nonlocal call_count
            call_count += 1
            # Return mock based on table being queried
            if "kline_day" in str(query):
                return mock_day_result
            else:
                return mock_min1_result

        async_session_mock.execute.side_effect = mock_execute_side_effect

        result = await get_available_intervals_for_symbol(
            session=async_session_mock,
            symbol="600000.SH",
            interval_model_map={"day": KlineDay, "min1": INTERVAL_MODEL_MAP["min1"]},
        )

        # Should include day since it has data
        assert "day" in result
        # Should not include min1 since no data
        assert "min1" not in result


@pytest.mark.asyncio
class TestGetDataRangeForSymbolAsync:
    """Tests for get_data_range_for_symbol function."""

    async def test_returns_min_max_dates(self, async_session_mock):
        """Test that function returns (min_date, max_date) tuple."""
        min_date = datetime(2024, 1, 1)
        max_date = datetime(2025, 1, 31)

        mock_result = MagicMock()
        mock_result.first.return_value = (min_date, max_date)
        async_session_mock.execute.return_value = mock_result

        result = await get_data_range_for_symbol(
            session=async_session_mock,
            symbol="600000.SH",
            interval="day",
            interval_model_map=INTERVAL_MODEL_MAP,
        )

        assert result[0] == min_date
        assert result[1] == max_date

    async def test_returns_none_for_empty_symbol(self, async_session_mock):
        """Test that function returns (None, None) for symbol with no data."""
        mock_result = MagicMock()
        mock_result.first.return_value = (None, None)
        async_session_mock.execute.return_value = mock_result

        result = await get_data_range_for_symbol(
            session=async_session_mock,
            symbol="999999.SH",
            interval="day",
            interval_model_map=INTERVAL_MODEL_MAP,
        )

        assert result[0] is None
        assert result[1] is None

    async def test_raises_for_invalid_interval(self, async_session_mock):
        """Test that function raises ValueError for unsupported interval."""
        with pytest.raises(ValueError, match="不支持的周期"):
            await get_data_range_for_symbol(
                session=async_session_mock,
                symbol="600000.SH",
                interval="invalid_interval",
                interval_model_map=INTERVAL_MODEL_MAP,
            )
