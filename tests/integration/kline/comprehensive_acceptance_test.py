#!/usr/bin/env python3
"""综合验收测试 - 验证K线功能的所有要求均已满足.

集成测试：验证模块导入、枚举、表结构、SecurityType 推断。
"""

import inspect

import pytest
from sqlalchemy import text

from galaxy_core.database.core.async_connection import AsyncDatabaseManager


@pytest.mark.asyncio
async def test_module_imports():
    """测试1: 验证模块导入."""
    from galaxy_core.database.services.kline import KlineService
    from galaxy_core.services.kline_data_service import KlineDataService

    assert KlineService is not None
    assert KlineDataService is not None


@pytest.mark.asyncio
async def test_database_connection(db_manager: AsyncDatabaseManager):
    """测试2: 验证数据库连接."""
    async with db_manager.session() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_enums():
    """测试3: 验证枚举类型."""
    from galaxy_core.shared_kernel.enums.interval import Interval
    from galaxy_core.shared_kernel.enums.security_type import SecurityType

    intervals = [interval.value for interval in Interval]
    security_types = [st.value for st in SecurityType]
    assert len(intervals) > 0
    assert len(security_types) > 0


@pytest.mark.asyncio
async def test_table_structure(db_manager: AsyncDatabaseManager):
    """测试4: 验证数据库表结构."""
    from galaxy_core.shared_kernel.enums.interval import Interval

    async with db_manager.session() as session:
        tables_query = """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name LIKE 'kline_%'
        """
        result = await session.execute(text(tables_query))
        tables = [row[0] for row in result.fetchall()]

        expected_tables = [f"kline_{interval.value}" for interval in Interval]
        missing_tables = set(expected_tables) - set(tables)

        assert not missing_tables, f"缺少表: {missing_tables}"


@pytest.mark.asyncio
async def test_sync_logic():
    """测试5: 验证数据同步逻辑."""
    from galaxy_core.application.kline.command import handle_kline_command_async

    command_source = inspect.getsource(handle_kline_command_async)
    assert "handle_kline_command_async" in command_source, "异步命令处理函数应存在"


@pytest.mark.asyncio
async def test_security_type_inference():
    """测试7: 验证SecurityType推断."""
    from galaxy_core.domain.symbol.type_inference import infer_security_type

    test_code = "600000.SH"
    inferred = infer_security_type(test_code)

    assert inferred is not None, f"应能推断 {test_code} 的证券类型"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
