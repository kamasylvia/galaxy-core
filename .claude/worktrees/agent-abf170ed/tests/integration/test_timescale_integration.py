#!/usr/bin/env python3
"""TimescaleDB 集成测试."""

import os
from src.galaxy_db_bridge.database.core import init_database, create_kline_hypertables


def test_timescale_integration():
    """测试 TimescaleDB 集成."""
    print("开始测试 TimescaleDB 集成...")

    # 初始化数据库连接 (使用环境变量或默认值)
    db_manager = init_database(create_tables=False)  # 先不创建表

    print("数据库连接初始化成功")

    # 手动创建表
    db_manager.create_tables()
    print("数据表创建完成")

    # 尝试创建 hypertables
    create_kline_hypertables()
    print("TimescaleDB hypertables 创建完成")

    print("TimescaleDB 集成测试成功!")


if __name__ == "__main__":
    test_timescale_integration()
