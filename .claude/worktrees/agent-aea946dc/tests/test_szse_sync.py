from datetime import date
from unittest.mock import MagicMock, patch

from galaxy_db_sync.database.models.trading_calendar import TradingCalendar
from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service


@patch("galaxy_db_sync.database.services.trading_calendar.db_manager")
def test_sync_calendar_refreshes_shared_calendar(mock_db_manager):
    """交易日历同步只按年份刷新共享交易日历。"""
    session = MagicMock()
    mock_db_manager.get_session.return_value = session

    trading_days = [date(2020, 1, 2), date(2020, 1, 3)]

    with (
        patch.object(
            trading_calendar_service,
            "_fetch_from_akshare",
            return_value=trading_days,
        ) as mock_fetch,
        patch.object(trading_calendar_service, "_save_to_db") as mock_save,
    ):
        count = trading_calendar_service.sync_calendar(2020)

    assert count == 2
    mock_fetch.assert_called_once_with(date(2020, 1, 1), date(2020, 12, 31))
    mock_save.assert_called_once_with(trading_days)

    filter_arg = session.query.return_value.filter.call_args.args[0]
    assert str(filter_arg) == str(TradingCalendar.year == 2020)
    session.query.return_value.filter.return_value.delete.assert_called_once_with()
    session.commit.assert_called_once()
    session.close.assert_called_once()
