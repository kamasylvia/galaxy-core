"""缺失数据追踪服务异步方法测试."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch


class TestMissingDataTrackerAsync:
    """缺失数据追踪异步方法测试类."""

    @pytest.mark.asyncio
    async def test_record_missing_range_async_skips_on_database_not_initialized(self):
        """测试数据库未初始化时异步记录安全跳过."""
        mock_session_context = MagicMock()
        mock_session_context.__aenter__ = AsyncMock(
            side_effect=RuntimeError("Database not initialized.")
        )
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "galaxy_db_sync.database.core.async_connection.async_db_manager.session",
            return_value=mock_session_context,
        ):
            from galaxy_db_sync.database.services.missing_data_tracker import (
                MissingDataTracker,
            )
            tracker = MissingDataTracker()
            # 不应抛出异常，应安全跳过
            await tracker.record_missing_range_async(
                "600519.SH", "day",
                date(2024, 1, 1), date(2024, 1, 31),
                date(2024, 1, 15), date(2024, 1, 20),
            )

    @pytest.mark.asyncio
    async def test_is_range_confirmed_missing_async_returns_false_on_database_not_initialized(self):
        """测试数据库未初始化时异步检查返回 False."""
        mock_session_context = MagicMock()
        mock_session_context.__aenter__ = AsyncMock(
            side_effect=RuntimeError("Database not initialized.")
        )
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "galaxy_db_sync.database.core.async_connection.async_db_manager.session",
            return_value=mock_session_context,
        ):
            from galaxy_db_sync.database.services.missing_data_tracker import (
                MissingDataTracker,
            )
            tracker = MissingDataTracker()
            result = await tracker.is_range_confirmed_missing_async(
                "600519.SH", "day",
                date(2024, 1, 1), date(2024, 1, 5),
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_get_known_missing_ranges_async_returns_empty_on_database_not_initialized(self):
        """测试数据库未初始化时返回空列表."""
        mock_session_context = MagicMock()
        mock_session_context.__aenter__ = AsyncMock(
            side_effect=RuntimeError("Database not initialized.")
        )
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "galaxy_db_sync.database.core.async_connection.async_db_manager.session",
            return_value=mock_session_context,
        ):
            from galaxy_db_sync.database.services.missing_data_tracker import (
                MissingDataTracker,
            )
            tracker = MissingDataTracker()
            result = await tracker.get_known_missing_ranges_async(
                "600519.SH", "day",
                date(2024, 1, 1), date(2024, 1, 31),
            )
            assert result == []

    @pytest.mark.asyncio
    async def test_get_confirmed_missing_ranges_async_returns_empty_on_database_not_initialized(self):
        """测试数据库未初始化时已确认缺失返回空列表."""
        mock_session_context = MagicMock()
        mock_session_context.__aenter__ = AsyncMock(
            side_effect=RuntimeError("Database not initialized.")
        )
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "galaxy_db_sync.database.core.async_connection.async_db_manager.session",
            return_value=mock_session_context,
        ):
            from galaxy_db_sync.database.services.missing_data_tracker import (
                MissingDataTracker,
            )
            tracker = MissingDataTracker()
            result = await tracker.get_confirmed_missing_ranges_async(
                "600519.SH", "day",
            )
            assert result == []

    @pytest.mark.asyncio
    async def test_clear_resolved_missing_async_skips_on_database_not_initialized(self):
        """测试数据库未初始化时清除操作安全跳过."""
        mock_session_context = MagicMock()
        mock_session_context.__aenter__ = AsyncMock(
            side_effect=RuntimeError("Database not initialized.")
        )
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "galaxy_db_sync.database.core.async_connection.async_db_manager.session",
            return_value=mock_session_context,
        ):
            from galaxy_db_sync.database.services.missing_data_tracker import (
                MissingDataTracker,
            )
            tracker = MissingDataTracker()
            # 不应抛出异常
            await tracker.clear_resolved_missing_async(
                "600519.SH", "day",
                date(2024, 1, 15), date(2024, 1, 20),
            )

    @pytest.mark.asyncio
    async def test_confirm_missing_as_api_empty_async_skips_on_database_not_initialized(self):
        """测试数据库未初始化时确认操作安全跳过."""
        mock_session_context = MagicMock()
        mock_session_context.__aenter__ = AsyncMock(
            side_effect=RuntimeError("Database not initialized.")
        )
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "galaxy_db_sync.database.core.async_connection.async_db_manager.session",
            return_value=mock_session_context,
        ):
            from galaxy_db_sync.database.services.missing_data_tracker import (
                MissingDataTracker,
            )
            tracker = MissingDataTracker()
            # 不应抛出异常
            await tracker.confirm_missing_as_api_empty_async(
                "600519.SH", "day",
                date(2024, 1, 15), date(2024, 1, 20),
                api_response="empty",
            )

    @pytest.mark.asyncio
    async def test_confirm_missing_as_synced_async_skips_on_database_not_initialized(self):
        """测试数据库未初始化时标记已同步操作安全跳过."""
        mock_session_context = MagicMock()
        mock_session_context.__aenter__ = AsyncMock(
            side_effect=RuntimeError("Database not initialized.")
        )
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "galaxy_db_sync.database.core.async_connection.async_db_manager.session",
            return_value=mock_session_context,
        ):
            from galaxy_db_sync.database.services.missing_data_tracker import (
                MissingDataTracker,
            )
            tracker = MissingDataTracker()
            # 不应抛出异常
            await tracker.confirm_missing_as_synced_async(
                "600519.SH", "day",
                date(2024, 1, 15), date(2024, 1, 20),
            )