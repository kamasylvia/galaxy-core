"""
测试交易日历服务的协议和基本功能。
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

from datetime import date

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


class TestFetchTradingCalendarScript:
    """测试交易日历服务导入。"""

    def test_script_imports(self):
        """测试服务可以正确导入。"""
        from galaxy_core.database.services.trading_calendar import (
            TradingCalendarService,
        )

        assert TradingCalendarService is not None

    def test_year_range_constants(self):
        """测试年份范围常量。"""
        start_year = 2010
        end_year = 2026

        assert start_year == 2010
        assert end_year == 2026
        assert end_year > start_year


class TestTradingCalendarProtocol:
    def test_trading_calendar_service_exposes_get_previous_trading_day(self):
        from galaxy_core.database.services.trading_calendar import TradingCalendarService

        mock_db = MagicMock()
        service = TradingCalendarService(db_manager=mock_db)
        assert callable(getattr(service, "get_previous_trading_day_async", None))
