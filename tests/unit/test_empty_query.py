"""空查询缓存测试模块.

测试 empty_query_service 的功能，包括：
- 数据库未初始化时的安全回退
- 空查询结果记录
"""

import unittest
from datetime import date
from unittest.mock import patch, AsyncMock, MagicMock


class TestEmptyQueryCache(unittest.TestCase):
    """空查询缓存测试类."""

    def test_empty_query_cache_check_returns_false_when_database_not_initialized(self):
        """测试数据库未初始化时空查询缓存检查安全回退为 False."""
        with patch(
            "galaxy_db_sync.database.services.empty_query.db_manager.session",
            side_effect=RuntimeError("Database not initialized. Call initialize() first."),
        ):
            from galaxy_db_sync.database.services.empty_query import (
                empty_query_service,
            )

            result = empty_query_service.is_confirmed_empty(
                "600519.SH",
                "day",
                date(2024, 1, 1),
                date(2024, 1, 5),
            )

        self.assertFalse(result)

    def test_empty_query_cache_record_skips_when_database_not_initialized(self):
        """测试数据库未初始化时空查询缓存写入直接跳过."""
        with patch(
            "galaxy_db_sync.database.services.empty_query.db_manager.session",
            side_effect=RuntimeError("Database not initialized. Call initialize() first."),
        ):
            from galaxy_db_sync.database.services.empty_query import (
                empty_query_service,
            )

            result = empty_query_service.record_empty_result(
                "600519.SH",
                "day",
                date(2024, 1, 1),
                date(2024, 1, 5),
            )

        self.assertIsNone(result)


class TestEmptyQueryCacheAsync(unittest.TestCase):
    """空查询缓存异步方法测试类."""

    def test_is_confirmed_empty_async_returns_false_on_database_not_initialized(self):
        """测试数据库未初始化时异步检查返回 False."""
        async def run_test():
            mock_session_context = MagicMock()
            mock_session_context.__aenter__ = AsyncMock(
                side_effect=RuntimeError("Database not initialized.")
            )
            mock_session_context.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "galaxy_db_sync.database.core.async_connection.async_db_manager.session",
                return_value=mock_session_context,
            ):
                from galaxy_db_sync.database.services.empty_query import (
                    EmptyQueryResultService,
                )
                service = EmptyQueryResultService()
                result = await service.is_confirmed_empty_async(
                    "600519.SH", "day",
                    date(2024, 1, 1), date(2024, 1, 5),
                )
                return result

        import asyncio
        result = asyncio.run(run_test())
        self.assertFalse(result)

    def test_record_empty_result_async_skips_on_database_not_initialized(self):
        """测试数据库未初始化时异步写入安全跳过."""
        async def run_test():
            mock_session_context = MagicMock()
            mock_session_context.__aenter__ = AsyncMock(
                side_effect=RuntimeError("Database not initialized.")
            )
            mock_session_context.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "galaxy_db_sync.database.core.async_connection.async_db_manager.session",
                return_value=mock_session_context,
            ):
                from galaxy_db_sync.database.services.empty_query import (
                    EmptyQueryResultService,
                )
                service = EmptyQueryResultService()
                await service.record_empty_result_async(
                    "600519.SH", "day",
                    date(2024, 1, 1), date(2024, 1, 5),
                )

        import asyncio
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
