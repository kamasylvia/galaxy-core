"""Tests for retry_handler."""

import pytest
from unittest.mock import AsyncMock
from galaxy_db_sync.application.scheduler.retry_handler import sync_with_retry, RetryPolicy


class TestRetryPolicy:
    """Tests for RetryPolicy configuration."""

    def test_default_max_retries(self):
        """Default max retries is 3."""
        assert RetryPolicy.MAX_RETRIES == 3

    def test_retry_delays_from_config(self):
        """Retry delays are loaded from config."""
        RetryPolicy.from_config()
        # Config in conftest.py sets [5, 15, 30] minutes
        assert RetryPolicy.RETRY_DELAYS == [300, 900, 1800]  # in seconds


class TestSyncWithRetry:
    """Tests for sync_with_retry function."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self, mock_sync_func):
        """Returns True immediately on success."""
        mock_sync_func.return_value = True
        result = await sync_with_retry(mock_sync_func, "test_sync")
        assert result is True
        assert mock_sync_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self, mock_sync_func):
        """Retries up to MAX_RETRIES times."""
        mock_sync_func.side_effect = Exception("Sync failed")
        # Mock sleep to avoid long waits in tests
        import galaxy_db_sync.application.scheduler.retry_handler as rh
        original_sleep = rh.asyncio.sleep
        rh.asyncio.sleep = AsyncMock()

        result = await sync_with_retry(mock_sync_func, "test_sync")
        assert result is False
        assert mock_sync_func.call_count == 3  # MAX_RETRIES

        rh.asyncio.sleep = original_sleep

    @pytest.mark.asyncio
    async def test_success_after_retry(self, mock_sync_func):
        """Succeeds after some retries."""
        mock_sync_func.side_effect = [
            Exception("First failure"),
            Exception("Second failure"),
            True,  # Success on third attempt
        ]
        import galaxy_db_sync.application.scheduler.retry_handler as rh
        original_sleep = rh.asyncio.sleep
        rh.asyncio.sleep = AsyncMock()

        result = await sync_with_retry(mock_sync_func, "test_sync")
        assert result is True
        assert mock_sync_func.call_count == 3

        rh.asyncio.sleep = original_sleep