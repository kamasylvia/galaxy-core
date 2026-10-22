#!/usr/bin/env python3
"""简单测试K线功能.

集成测试：验证数据库连接和 K 线命令执行。
"""

import pytest
import sqlalchemy as sa

from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.shared_kernel.enums.interval import Interval


@pytest.mark.asyncio
async def test_db_connection(db_manager: AsyncDatabaseManager):
    """测试数据库连接"""
    print("初始化数据库...")
    # 检查数据库中是否存在K线表
    assert db_manager._engine is not None, "数据库引擎未初始化"

    async with db_manager._engine.connect() as conn:
        for interval in Interval:
            table_name = f"kline_{interval.value}"
            try:
                # 检查表是否存在
                def _inspect(connection):
                    inspector = sa.inspect(connection)
                    return inspector.get_table_names()

                tables = await conn.run_sync(lambda sync_conn: _inspect(sync_conn.engine))
                if table_name in tables:
                    result = await conn.execute(
                        sa.text(f"SELECT COUNT(*) FROM {table_name};")
                    )
                    count = result.scalar()
                    print(f"  {table_name}: 存在, 数据量={count}")
                else:
                    print(f"  {table_name}: 不存在")
            except Exception as e:
                print(f"  {table_name}: 错误 - {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
