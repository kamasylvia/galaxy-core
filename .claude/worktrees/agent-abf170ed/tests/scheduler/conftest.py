"""Shared fixtures for scheduler tests."""

import sys
import importlib.util
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import date

# Mock AmazingData SDK before any imports that depend on it
# This allows test fixtures to load without the private SDK dependencies
sys.modules["AmazingData"] = MagicMock()

# Mock akshare to avoid dependency chain in tests
sys.modules["akshare"] = MagicMock()

# Load Interval directly from file path to bypass package __init__.py
# which imports AmazingDataClient and triggers the SDK dependency chain
spec = importlib.util.spec_from_file_location(
    "interval",
    "src/galaxy_db_bridge/shared_kernel/enums/interval.py",
)
interval_module = importlib.util.module_from_spec(spec)
sys.modules["galaxy_db_bridge.shared_kernel.enums.interval"] = interval_module
spec.loader.exec_module(interval_module)
Interval = interval_module.Interval


@pytest.fixture
def mock_state_manager():
    """Mock SyncStateManager."""
    manager = MagicMock()
    manager.is_synced = AsyncMock(return_value=False)
    manager.mark_running = AsyncMock()
    manager.mark_success = AsyncMock()
    manager.mark_failed = AsyncMock()
    manager.get_retry_count = AsyncMock(return_value=0)
    return manager


@pytest.fixture
def mock_boundary_checker():
    """Mock IntervalBoundaryChecker.

    Will use spec=IntervalBoundaryChecker once the class exists.
    """
    checker = MagicMock()
    checker.is_last_trading_day_of_period = AsyncMock(return_value=False)
    checker.get_periods_to_sync_today = AsyncMock(return_value=[Interval.DAY])
    return checker


@pytest.fixture
def mock_sync_func():
    """Mock sync function for retry tests."""
    return AsyncMock(return_value=True)


@pytest.fixture
def mock_calendar_service():
    """Mock TradingCalendarService."""
    service = MagicMock()
    service.sync_calendar = AsyncMock(return_value=250)
    service.get_trading_days = AsyncMock(return_value=[])
    return service