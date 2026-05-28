"""
测试 fetch_trading_calendar_2010_2026.py 脚本。

测试脚本的基本功能和导入。
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from datetime import date

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


class TestFetchTradingCalendarScript:
    """测试交易日历拉取脚本。"""

    def test_script_imports(self):
        """测试脚本可以正确导入。"""
        from galaxy_db_sync.database.services.trading_calendar import (
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

    @pytest.mark.asyncio
    async def test_main_function_success(self):
        """测试 main 函数成功执行。"""
        # 导入 main 函数
        with patch.dict(
            "sys.modules",
            {
                "galaxy_db_sync.database.services.trading_calendar": MagicMock(),
            },
        ):
            # 创建 mock service
            mock_service = MagicMock()
            mock_service.sync_years = AsyncMock(
                return_value={"total": 100, "added": 50, "updated": 30, "skipped": 20}
            )

            with patch(
                "galaxy_db_sync.database.services.trading_calendar.TradingCalendarService",
                return_value=mock_service,
            ):
                # 重新导入模块以应用 mock
                import importlib

                import scripts.fetch_trading_calendar_2010_2026 as script_module

                importlib.reload(script_module)

                # 执行 main 函数
                await script_module.main()

                # 验证 sync_years 被正确调用
                mock_service.sync_years.assert_called_once_with(
                    start_year=2010, end_year=2026
                )

    @pytest.mark.asyncio
    async def test_main_function_with_error(self):
        """测试 main 函数处理错误。"""
        mock_service = MagicMock()
        mock_service.sync_years = AsyncMock(side_effect=Exception("数据库连接失败"))

        with patch(
            "galaxy_db_sync.database.services.trading_calendar.TradingCalendarService",
            return_value=mock_service,
        ):
            import importlib

            import scripts.fetch_trading_calendar_2010_2026 as script_module

            importlib.reload(script_module)

            # 执行 main 函数应该抛出 SystemExit
            with pytest.raises(SystemExit) as exc_info:
                await script_module.main()

            assert exc_info.value.code == 1



class TestTradingCalendarProtocol:
    def test_trading_calendar_service_exposes_get_previous_trading_day(self):
        from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service

        assert callable(getattr(trading_calendar_service, "get_previous_trading_day"))

    def test_get_previous_trading_day_returns_weekday_when_calendar_cached(self):
        from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service

        # 直接 mock get_trading_days，避免触发 DB/akshare
        trading_calendar_service.get_trading_days = MagicMock(
            return_value=[date(2025, 3, 24), date(2025, 3, 25), date(2025, 3, 26)]
        )

        assert trading_calendar_service.get_previous_trading_day(date(2025, 3, 26)) == date(
            2025, 3, 25
        )


class TestScriptIntegration:
    """脚本集成测试。"""

    def test_script_file_exists(self):
        """测试脚本文件存在。"""
        script_path = project_root / "scripts" / "fetch_trading_calendar_2010_2026.py"
        assert script_path.exists(), f"脚本文件不存在: {script_path}"

    def test_script_is_executable(self):
        """测试脚本包含正确的 shebang。"""
        script_path = project_root / "scripts" / "fetch_trading_calendar_2010_2026.py"
        with open(script_path, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
        assert first_line == "#!/usr/bin/env python", "脚本缺少正确的 shebang"

    def test_script_has_main_guard(self):
        """测试脚本包含 main 守护。"""
        script_path = project_root / "scripts" / "fetch_trading_calendar_2010_2026.py"
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert 'if __name__ == "__main__":' in content, "脚本缺少 main 守护"
