#!/usr/bin/env python3
"""简单测试K线功能"""

from galaxy_db_sync.database.core.connection import db_manager


def test_db_connection():
    """测试数据库连接"""
    print("初始化数据库...")
    try:
        db_manager.initialize()
        print("数据库初始化成功!")

        # 检查数据库中是否存在K线表
        from galaxy_db_sync.shared_kernel.enums.interval import Interval
        import sqlalchemy as sa

        if hasattr(db_manager, "_engine") and db_manager._engine:
            with db_manager._engine.connect() as conn:
                for interval in Interval:
                    table_name = f"kline_{interval.value}"
                    try:
                        # 检查表是否存在
                        inspector = sa.inspect(db_manager._engine)
                        if table_name in inspector.get_table_names():
                            # 获取表中数据量
                            result = conn.execute(
                                sa.text(f"SELECT COUNT(*) FROM {table_name};")
                            )
                            count = result.scalar()
                            print(f"  {table_name}: 存在, 数据量={count}")
                        else:
                            print(f"  {table_name}: 不存在")
                    except Exception as e:
                        print(f"  {table_name}: 错误 - {e}")
        else:
            print("  数据库引擎未初始化")
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        raise AssertionError("数据库初始化失败") from e


def test_kline_command():
    """测试kline命令"""
    print("\n测试K线命令...")

    # 先尝试初始化数据库
    try:
        db_manager.initialize()
        print("数据库已初始化")
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        raise AssertionError("数据库初始化失败") from e

    # 测试获取单个证券的K线数据
    from galaxy_db_sync.application.kline.command import handle_kline_command
    import argparse

    # 创建参数对象
    args = argparse.Namespace()
    args.symbols = "600000.SH"
    args.interval = "day"
    args.start = "20230101"
    args.end = "20230110"  # 只获取少量数据进行测试

    try:
        result = handle_kline_command(args)
        print(f"K线命令执行结果: {result}")
        assert result == 0
    except Exception as e:
        print(f"K线命令执行失败: {e}")
        import traceback

        traceback.print_exc()
        raise AssertionError("K线命令执行失败") from e


if __name__ == "__main__":
    print("=== 简单K线功能测试 ===")

    # 测试数据库连接
    db_ok = test_db_connection()

    if db_ok:
        # 测试K线命令
        cmd_ok = test_kline_command()
        print(
            f"\n测试结果: 数据库={'✓' if db_ok else '✗'}, 命令={'✓' if cmd_ok else '✗'}"
        )
    else:
        print("数据库连接失败，跳过命令测试")

    print("测试完成!")
