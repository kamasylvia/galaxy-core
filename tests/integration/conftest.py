"""集成测试共享 fixture — AsyncDatabaseManager 的 event loop 兼容处理.

每个 async test 独享一个 AsyncDatabaseManager 实例，确保 engine 和
session 在同一 event loop 创建，避免 "Future attached to a different
loop" 错误。
"""

import pytest_asyncio

from galaxy_core.database.core.async_connection import AsyncDatabaseManager


@pytest_asyncio.fixture
async def db_manager():
    """创建并初始化 AsyncDatabaseManager（每个测试独享，同一 event loop）."""
    manager = AsyncDatabaseManager()
    manager.initialize()
    yield manager

    await manager.close()


@pytest_asyncio.fixture
async def db_session(db_manager):
    """提供异步数据库会话."""
    async with db_manager.session() as session:
        yield session
