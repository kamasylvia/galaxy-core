#!/usr/bin/env python3
"""
更新数据库中已有数据的 security_type 脚本

此脚本将遍历所有 K 线表，根据证券代码更新其 security_type 字段，
以修正之前可能错误的类型标识。
"""

import sys
import os
from typing import Dict, Type
from sqlalchemy import create_engine, inspect, func
from sqlalchemy.orm import sessionmaker

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

# 导入数据库模型
from galaxy_db_sync.database.models.kline import (
    BaseKline,
    INTERVAL_MODEL_MAP,
    KlineMin1,
    KlineMin3,
    KlineMin5,
    KlineMin10,
    KlineMin15,
    KlineMin30,
    KlineMin60,
    KlineMin120,
    KlineDay,
    KlineWeek,
    KlineMonth,
    KlineSeason,
    KlineYear,
)
from galaxy_db_sync.shared_kernel.utils import infer_security_type
from galaxy_db_sync.database.core.connection import db_manager


def update_security_types():
    """更新数据库中所有表的 security_type 字段"""

    # 初始化数据库
    db_manager.initialize()
    engine = db_manager._engine
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 获取所有K线表
    tables_to_update = list(INTERVAL_MODEL_MAP.values())

    print(f"开始更新 {len(tables_to_update)} 个K线表的 security_type...")

    total_updated = 0

    for table_model in tables_to_update:
        table_name = table_model.__tablename__
        print(f"\n正在处理表: {table_name}")

        try:
            # 计算表中的总记录数
            with SessionLocal() as session:
                total_records = session.query(table_model).count()
                print(f"  表中共有 {total_records} 条记录")

                # 分批处理记录，避免内存问题
                batch_size = 1000
                offset = 0
                batch_updated = 0

                while True:
                    # 获取一批记录
                    records = (
                        session.query(table_model)
                        .offset(offset)
                        .limit(batch_size)
                        .all()
                    )

                    if not records:
                        break

                    # 处理这批记录
                    for record in records:
                        # 推断正确的 security_type
                        correct_type = infer_security_type(record.symbol)

                        # 如果当前的 security_type 与推断的不一致，则更新
                        if record.security_type != correct_type:
                            old_type = record.security_type
                            record.security_type = correct_type

                            # 打印更新信息（只打印前10个）
                            if batch_updated < 10:
                                print(
                                    f"    更新: {record.symbol} '{old_type}' -> '{correct_type}'"
                                )
                            elif batch_updated == 10:
                                print(f"    ... (省略更多更新)")

                            batch_updated += 1

                    # 提交当前批次的更改
                    session.commit()

                    print(
                        f"    批次 {offset//batch_size + 1}: 处理了 {len(records)} 条记录"
                    )

                    offset += batch_size

                    # 如果记录数少于批次大小，说明已经处理完所有记录
                    if len(records) < batch_size:
                        break

                print(f"  表 {table_name} 更新完成，共更新 {batch_updated} 条记录")
                total_updated += batch_updated

        except Exception as e:
            print(f"  处理表 {table_name} 时出错: {e}")
            continue

    print(f"\n所有表处理完成！总共更新了 {total_updated} 条记录")

    # 显示更新统计
    print("\n更新统计:")
    with SessionLocal() as session:
        for table_model in tables_to_update:
            table_name = table_model.__tablename__
            # 统计各类 security_type 的数量
            result = (
                session.query(table_model.security_type, func.count(table_model.id))
                .group_by(table_model.security_type)
                .all()
            )

            print(f"  {table_name}:")
            for sec_type, count in result:
                print(f"    {sec_type}: {count}")


def preview_changes():
    """预览将要进行的更改"""

    # 初始化数据库
    db_manager.initialize()
    engine = db_manager._engine
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    print("预览将要进行的 security_type 更新:")

    # 只检查一个表作为样本
    sample_table = KlineDay  # 使用日线表作为样本
    table_name = sample_table.__tablename__

    with SessionLocal() as session:
        # 获取前100条记录进行预览
        sample_records = session.query(sample_table).limit(100).all()

        updates_preview = []
        for record in sample_records:
            correct_type = infer_security_type(record.symbol)
            if record.security_type != correct_type:
                updates_preview.append(
                    {
                        "symbol": record.symbol,
                        "old_type": record.security_type,
                        "new_type": correct_type,
                    }
                )

        print(
            f"\n在 {table_name} 表的前100条记录中，发现 {len(updates_preview)} 个需要更新的记录:"
        )
        for i, update in enumerate(updates_preview[:10]):  # 只显示前10个
            print(
                f"  {update['symbol']}: '{update['old_type']}' -> '{update['new_type']}'"
            )

        if len(updates_preview) > 10:
            print(f"  ... 还有 {len(updates_preview) - 10} 个需要更新")

        print(f"\n总共在样本中发现 {len(updates_preview)} 个需要更新的记录")


if __name__ == "__main__":
    from sqlalchemy import func  # 导入func用于统计

    if len(sys.argv) > 1 and sys.argv[1] == "--preview":
        preview_changes()
    else:
        print("此脚本将更新数据库中所有K线表的 security_type 字段")
        print("根据最新的 infer_security_type 函数推断正确的类型")

        response = input("\n是否继续? (y/N): ")
        if response.lower() in ["y", "yes"]:
            update_security_types()
        else:
            print("操作已取消")
