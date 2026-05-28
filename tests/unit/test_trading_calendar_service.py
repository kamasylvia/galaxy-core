"""交易日历服务单元测试模块.

测试 trading_calendar_service 的功能，包括：
- 缓存命中日志
"""

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch, MagicMock


class TestTradingCalendarService(unittest.TestCase):
    """交易日历服务单元测试类."""

    @patch("galaxy_db_sync.database.services.trading_calendar.logger")
    @patch("galaxy_db_sync.database.services.trading_calendar.db_manager")
    def test_get_trading_days_logs_cache_hit(self, mock_db_manager, mock_logger):
        """测试交易日历完整命中缓存时会输出命中日志."""
        session = MagicMock()
        mock_db_manager.get_session.return_value = session
        session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            SimpleNamespace(trade_date=date(2017, 4, 5), is_trading_day=True),
            SimpleNamespace(trade_date=date(2017, 4, 6), is_trading_day=True),
            SimpleNamespace(trade_date=date(2017, 4, 7), is_trading_day=True),
        ]

        from galaxy_db_sync.database.services.trading_calendar import (
            trading_calendar_service,
        )

        result = trading_calendar_service.get_trading_days(
            date(2017, 4, 5),
            date(2017, 4, 7),
        )

        self.assertEqual(
            result,
            [date(2017, 4, 5), date(2017, 4, 6), date(2017, 4, 7)],
        )
        mock_logger.info.assert_any_call(
            "交易日历缓存命中: range=2017-04-05~2017-04-07, calendar_rows=3, trading_days=3"
        )
        session.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
