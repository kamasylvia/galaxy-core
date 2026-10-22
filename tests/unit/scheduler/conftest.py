"""Shared fixtures for scheduler tests."""

import importlib.util
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Mock AmazingData SDK before any imports that depend on it
# This allows test fixtures to load without the private SDK dependencies
sys.modules["AmazingData"] = MagicMock()

# Mock config_loader to return empty config sections
mock_config_loader = MagicMock()
mock_config_loader.get_section = MagicMock(
    return_value={
        "kline_trigger_hour": 23,
        "kline_trigger_minute": 0,
        "check_trigger_hour": 17,
        "check_trigger_minute": 0,
        "enabled_intervals": ["day", "week", "month", "season", "year"],
        "check_intervals": ["day", "week"],
        "security_type": "SH_A",
        "check_ranges": {
            "SH_A": {"start_year": 2013},
            "SZ_A": {"start_year": 2013},
            "BJ_A": {"start_year": 2013},
            "EXTRA_ETF": {"start_year": 2013},
            "SH_INDEX": {"start_year": 2013},
            "SZ_INDEX": {"start_year": 2013},
            "default": {"start_year": 2013},
        },
        "max_retries": 3,
        "retry_delay_minutes": 5,
        "routine_lookback_periods": 10,
        # kline 子表(2026-08-11):前缀匹配测试用
        "kline": {"max_retries": 6},
    }
)
sys.modules["galaxy_core.shared_kernel.utils.config_loader"] = mock_config_loader

# Load Interval directly from file path to bypass package __init__.py imports
# which imports AmazingDataClient and triggers the SDK dependency chain
spec = importlib.util.spec_from_file_location(
    "interval",
    "src/galaxy_core/shared_kernel/enums/interval.py",
)
interval_module = importlib.util.module_from_spec(spec)
sys.modules["galaxy_core.shared_kernel.enums.interval"] = interval_module
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
    checker.is_long_interval = MagicMock(
        side_effect=lambda i: i in {Interval.WEEK, Interval.MONTH, Interval.SEASON, Interval.YEAR}
    )
    checker.LONG_INTERVALS = {Interval.WEEK, Interval.MONTH, Interval.SEASON, Interval.YEAR}
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
