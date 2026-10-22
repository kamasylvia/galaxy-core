"""Pytest configuration and fixtures for unit tests.

This conftest.py provides:
1. AmazingData SDK mocking to avoid import errors
2. Trading calendar fixtures
3. Async database fixtures for testing AsyncDatabaseManager
"""

# Bootstrap mocking for AmazingData SDK before any imports
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# Register galaxy_core packages before AmazingData import
SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "galaxy_core"

for package_name, package_path in {
    "galaxy_core": SRC_ROOT,
    "galaxy_core.amazing_data": SRC_ROOT / "amazing_data",
    "galaxy_core.amazing_data.api": SRC_ROOT / "amazing_data" / "api",
}.items():
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(package_path)]
        sys.modules[package_name] = package

# Mock config_loader to avoid toml dependency
# get_config(section, key, default=None) — return default if provided, else {}
if "galaxy_core.shared_kernel.utils.config_loader" not in sys.modules:
    config_loader = types.ModuleType("galaxy_core.shared_kernel.utils.config_loader")

    def _mock_get_config(*args, **kwargs):
        # get_config(section, key, default=None)
        if len(args) >= 3:
            return args[2]
        return kwargs.get("default", None)

    config_loader.get_config = _mock_get_config
    config_loader.get_section = lambda *args, **kwargs: {}
    config_loader.load_config_dict = lambda *args, **kwargs: {}
    sys.modules["galaxy_core.shared_kernel.utils.config_loader"] = config_loader

# Mock AmazingData SDK
if "AmazingData" not in sys.modules:
    amazing_data = types.ModuleType("AmazingData")

    def login(*args, **kwargs):
        return None

    def logout(*args, **kwargs):
        return None

    class BaseData:
        def get_calendar(self, *args, **kwargs):
            return MagicMock()

    class InfoData:
        pass

    class MarketData:
        def __init__(self, *args, **kwargs):
            pass

    amazing_data.login = login
    amazing_data.logout = logout
    amazing_data.BaseData = BaseData
    amazing_data.InfoData = InfoData
    amazing_data.MarketData = MarketData
    sys.modules["AmazingData"] = amazing_data

# Mock akshare (used by trading_calendar.py)
if "akshare" not in sys.modules:
    akshare = types.ModuleType("akshare")

    def tool_trade_date_hist_sina(*args, **kwargs):
        import pandas as pd
        from datetime import date
        # Return a mock DataFrame with trading dates
        return pd.DataFrame({
            "trade_date": [
                "2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07",
                "2025-01-08", "2025-01-09", "2025-01-10", "2025-01-13",
            ]
        })

    akshare.tool_trade_date_hist_sina = tool_trade_date_hist_sina
    sys.modules["akshare"] = akshare

# Imports after AmazingData mocking (intentional order)  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from datetime import date, timedelta  # noqa: E402
from unittest.mock import AsyncMock  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture
def mock_trading_calendar():
    """Create a mock trading calendar for testing.

    Returns a mock that simulates a standard trading calendar:
    - Weekdays (Mon-Fri) are trading days
    - Weekends (Sat-Sun) are not trading days
    """
    calendar = MagicMock()

    def is_trading_day(d: date) -> bool:
        """Simple trading day logic: weekdays are trading days."""
        return d.weekday() < 5  # 0-4 are Mon-Fri

    def get_previous_trading_day(d: date) -> date:
        """Get the previous trading day."""
        prev_day = d - timedelta(days=1)
        while not is_trading_day(prev_day):
            prev_day -= timedelta(days=1)
        return prev_day

    def get_next_trading_day(d: date) -> date:
        """Get the next trading day."""
        next_day = d + timedelta(days=1)
        while not is_trading_day(next_day):
            next_day += timedelta(days=1)
        return next_day

    calendar.is_trading_day.side_effect = is_trading_day
    calendar.get_previous_trading_day.side_effect = get_previous_trading_day
    calendar.get_next_trading_day.side_effect = get_next_trading_day

    # Async versions for IntervalBoundaryChecker
    async def async_is_trading_day(d: date) -> bool:
        return is_trading_day(d)

    async def async_get_previous_trading_day(d: date) -> date:
        return get_previous_trading_day(d)

    async def async_get_next_trading_day(d: date) -> date:
        return get_next_trading_day(d)

    calendar.is_trading_day_async = AsyncMock(side_effect=async_is_trading_day)
    calendar.get_previous_trading_day_async = AsyncMock(side_effect=async_get_previous_trading_day)
    calendar.get_next_trading_day_async = AsyncMock(side_effect=async_get_next_trading_day)

    return calendar


@pytest.fixture
def mock_trading_calendar_with_holidays():
    """Create a mock trading calendar with specific holidays.

    Holidays included:
    - 2025-01-01 (New Year's Day)
    - 2025-02-17 (Presidents Day)
    - 2025-04-18 (Good Friday - approximate)
    """
    calendar = MagicMock()

    holidays = {
        date(2025, 1, 1),  # New Year's Day
        date(2025, 2, 17),  # Presidents Day
        date(2025, 4, 18),  # Good Friday
    }

    def is_trading_day(d: date) -> bool:
        """Trading day logic with holidays."""
        if d in holidays:
            return False
        return d.weekday() < 5

    def get_previous_trading_day(d: date) -> date:
        """Get the previous trading day."""
        from datetime import timedelta

        prev_day = d - timedelta(days=1)
        while not is_trading_day(prev_day):
            prev_day -= timedelta(days=1)
        return prev_day

    def get_next_trading_day(d: date) -> date:
        """Get the next trading day."""
        from datetime import timedelta

        next_day = d + timedelta(days=1)
        while not is_trading_day(next_day):
            next_day += timedelta(days=1)
        return next_day

    calendar.is_trading_day.side_effect = is_trading_day
    calendar.get_previous_trading_day.side_effect = get_previous_trading_day
    calendar.get_next_trading_day.side_effect = get_next_trading_day
    calendar.holidays = holidays

    return calendar


# Async database fixtures
@pytest.fixture
def async_session_mock():
    """Create a mock AsyncSession for testing.

    Returns a mock that simulates AsyncSession behavior:
    - execute() returns mock result
    - commit(), rollback(), close() are async methods
    """
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def async_engine_mock():
    """Create a mock AsyncEngine for testing."""
    engine = MagicMock()
    engine.dispose = AsyncMock()
    engine.begin = MagicMock()
    return engine


@pytest.fixture
def async_db_manager_mock(async_engine_mock, async_session_mock):
    """Create a mock AsyncDatabaseManager for testing.

    Returns a mock with:
    - Mocked engine and session_maker
    - session() context manager that yields async_session_mock and commits on exit
    - close() that disposes engine
    """
    manager = MagicMock()
    manager._engine = async_engine_mock

    # Create a mock session_maker that returns async_session_mock
    session_maker_mock = MagicMock(return_value=async_session_mock)
    manager._session_maker = session_maker_mock

    # Create async context manager for session() that simulates commit/rollback behavior
    @asynccontextmanager
    async def mock_session():
        try:
            yield async_session_mock
            await async_session_mock.commit()
        except Exception:
            await async_session_mock.rollback()
            raise
        finally:
            await async_session_mock.close()

    manager.session = mock_session

    # Create close() that disposes engine
    async def mock_close():
        if async_engine_mock:
            await async_engine_mock.dispose()

    manager.close = mock_close
    manager.create_tables = AsyncMock()

    return manager
