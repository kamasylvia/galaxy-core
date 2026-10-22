from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.database.services.trading_calendar import TradingCalendarService


@pytest.fixture
def mock_db():
    return MagicMock(spec=AsyncDatabaseManager)


@pytest.fixture
def service(mock_db):
    return TradingCalendarService(mock_db)


@pytest.mark.asyncio
async def test_sync_calendar_refreshes_shared_calendar(service, mock_db):
    """交易日历同步只按年份刷新共享交易日历。"""
    trading_days = [date(2020, 1, 2), date(2020, 1, 3)]

    mock_session = AsyncMock()
    mock_db.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_db.session.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch.object(
        service,
        "_fetch_from_akshare",
        return_value=trading_days,
    ), patch.object(
        service,
        "_save_to_db_async",
        new_callable=AsyncMock,
    ) as mock_save:
        count = await service.sync_calendar_async(2020)

    assert count == 2
