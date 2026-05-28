from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service


@patch("galaxy_db_sync.database.services.trading_calendar.db_manager")
def test_get_trading_days_fetches_shared_calendar(mock_db_manager):
    """缓存未命中时，保存共享交易日历。"""
    session = MagicMock()
    mock_db_manager.get_session.return_value = session

    calendar_query = MagicMock()
    calendar_query.filter.return_value.order_by.return_value.all.return_value = []

    trading_query = MagicMock()
    trading_query.filter.return_value.order_by.return_value.all.return_value = [
        SimpleNamespace(trade_date=date(2016, 1, 4)),
        SimpleNamespace(trade_date=date(2016, 1, 5)),
    ]

    session.query.side_effect = [calendar_query, trading_query]

    fetched_days = [date(2016, 1, 4), date(2016, 1, 5)]

    with (
        patch.object(
            trading_calendar_service,
            "_fetch_from_akshare",
            return_value=fetched_days,
        ) as mock_fetch,
        patch.object(trading_calendar_service, "_save_to_db") as mock_save,
    ):
        result = trading_calendar_service.get_trading_days(
            date(2016, 1, 1),
            date(2016, 1, 31),
        )

    assert result == fetched_days
    mock_fetch.assert_called_once_with(date(2016, 1, 1), date(2016, 1, 31))
    mock_save.assert_called_once_with(fetched_days, date(2016, 1, 1), date(2016, 1, 31))

    first_filter_arg = calendar_query.filter.call_args.args[0]
    second_filter_arg = trading_query.filter.call_args.args[0]
    assert first_filter_arg is not None
    assert second_filter_arg is not None
    session.close.assert_called_once()
