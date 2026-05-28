"""Tests for KlineService class (async implementation)."""

import pytest
from datetime import datetime, date
from unittest.mock import MagicMock, AsyncMock, patch
import pandas as pd

from galaxy_db_sync.database.services.kline import KlineService
from galaxy_db_sync.database.core.async_connection import AsyncDatabaseManager


class TestKlineServiceInit:
    """Tests for KlineService initialization."""

    def test_receives_async_database_manager_parameter(self, async_db_manager_mock):
        """Test that KlineService.__init__ receives AsyncDatabaseManager parameter."""
        service = KlineService(db_manager=async_db_manager_mock)

        assert service._db_manager == async_db_manager_mock

    def test_interval_model_map_initialized(self, async_db_manager_mock):
        """Test that interval_model_map is initialized from INTERVAL_MODEL_MAP."""
        from galaxy_db_sync.database.models.kline import INTERVAL_MODEL_MAP

        service = KlineService(db_manager=async_db_manager_mock)

        assert service.interval_model_map == INTERVAL_MODEL_MAP


@pytest.mark.asyncio
class TestKlineServiceQuery:
    """Tests for KlineService query methods."""

    async def test_query_kline_from_db_uses_injected_session(
        self, async_db_manager_mock, async_session_mock
    ):
        """Test that query uses injected session from db_manager."""
        service = KlineService(db_manager=async_db_manager_mock)

        # Mock a record
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

        result = await service.query_kline_from_db(
            symbols=["600000.SH"],
            interval="day",
        )

        assert "600000.SH" in result
        assert isinstance(result["600000.SH"], pd.DataFrame)

    async def test_query_with_date_range(self, async_db_manager_mock, async_session_mock):
        """Test that query with date range works."""
        service = KlineService(db_manager=async_db_manager_mock)

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

        result = await service.query_kline_from_db(
            symbols=["600000.SH"],
            start_date="20250101",
            end_date="20250131",
            interval="day",
        )

        assert "600000.SH" in result


class TestKlineServiceMerge:
    """Tests for merge_db_and_api_data (pure function, no async)."""

    def test_merge_empty_db_data(self, async_db_manager_mock):
        """Test merge when db_data is empty."""
        service = KlineService(db_manager=async_db_manager_mock)

        api_df = pd.DataFrame(
            {
                "open": [12.0],
                "high": [12.5],
                "low": [11.5],
                "close": [12.2],
                "volume": [2000000],
                "amount": [24000000.0],
            },
            index=[datetime(2025, 1, 17)],
        )

        api_data = {"600000.SH": api_df}

        result = service.merge_db_and_api_data({}, api_data)

        assert "600000.SH" in result
        pd.testing.assert_frame_equal(result["600000.SH"], api_df)

    def test_merge_empty_api_data(self, async_db_manager_mock):
        """Test merge when api_data is empty."""
        service = KlineService(db_manager=async_db_manager_mock)

        db_df = pd.DataFrame(
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

        db_data = {"600000.SH": db_df}

        result = service.merge_db_and_api_data(db_data, {})

        assert "600000.SH" in result
        pd.testing.assert_frame_equal(result["600000.SH"], db_df)

    def test_merge_overlapping_dates_keeps_last(self, async_db_manager_mock):
        """Test that overlapping dates keep last (api data)."""
        service = KlineService(db_manager=async_db_manager_mock)

        # Same date in both
        db_df = pd.DataFrame(
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

        api_df = pd.DataFrame(
            {
                "open": [12.0],  # Different values
                "high": [12.5],
                "low": [11.5],
                "close": [12.2],
                "volume": [2000000],
                "amount": [24000000.0],
            },
            index=[datetime(2025, 1, 15)],
        )  # Same date

        db_data = {"600000.SH": db_df}
        api_data = {"600000.SH": api_df}

        result = service.merge_db_and_api_data(db_data, api_data)

        # Should keep API data (last in concat)
        assert result["600000.SH"].loc[datetime(2025, 1, 15)]["close"] == 12.2


@pytest.mark.asyncio
class TestKlineServiceSave:
    """Tests for KlineService save methods."""

    async def test_batch_save_uses_injected_session(
        self, async_db_manager_mock, async_session_mock
    ):
        """Test that batch_save uses injected session."""
        service = KlineService(db_manager=async_db_manager_mock)

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

        result = await service.batch_save_kline_to_db(
            kline_dict=kline_dict,
            interval="day",
        )

        assert result == 1
        async_session_mock.execute.assert_called()


class TestGlobalSingleton:
    """Tests verifying global singleton exists."""

    def test_global_kline_service_exists(self):
        """Test that kline_service singleton exists."""
        from galaxy_db_sync.database.services import kline_service

        # Should have a global instance
        assert kline_service is not None
        assert isinstance(kline_service, KlineService)

    def test_service_must_be_instantiated_with_db_manager(self):
        """Test that service cannot be instantiated without db_manager."""
        # Should raise TypeError if no db_manager provided
        with pytest.raises(TypeError):
            KlineService()  # Missing required db_manager argument
