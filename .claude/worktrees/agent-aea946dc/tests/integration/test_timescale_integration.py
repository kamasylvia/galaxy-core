#!/usr/bin/env python3
"""TimescaleDB 集成测试."""

import asyncio
import os

from galaxy_db_sync.database.core.async_connection import async_db_manager, init_async_database
from galaxy_db_sync.database.core.timescale import create_kline_hypertables


async def test_timescale_integration_async():
    """测试 TimescaleDB 集成（异步版本）."""
    print("开始测试 TimescaleDB 集成...")

    # 初始化异步数据库连接
    manager = await init_async_database(create_tables=False)

    print("异步数据库连接初始化成功")

    # 手动创建表
    await manager.create_tables()
    print("数据表创建完成")

    # 尝试创建 hypertables（使用异步版本）
    async with manager.session() as session:
        await create_kline_hypertables(session)
    print("TimescaleDB hypertables 创建完成")

    print("TimescaleDB 集成测试成功!")


def test_timescale_integration():
    """同步入口，驱动异步测试."""
    asyncio.run(test_timescale_integration_async())


if __name__ == "__main__":
    test_timescale_integration()
