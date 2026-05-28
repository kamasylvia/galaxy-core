#!/usr/bin/env python3
"""K 线表主键迁移回滚脚本：从备份表恢复原始表结构.

执行流程：
1. 查找指定表的备份表
2. 删除当前新表
3. 从备份表恢复原始表结构（包含 id 列）
4. 重建 hypertable
5. 可选：删除备份表

Usage:
    python scripts/rollback_pk_migration.py [--timestamp YYYYMMDD_HHMMSS] [--table kline_day] [--all]
"""

import asyncio
import argparse
import logging
import sys

from sqlalchemy import text

from galaxy_db_sync.database.core.async_connection import async_db_manager
from galaxy_db_sync.database.core.timescale import create_hypertable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

KLINE_TABLES = [
    "kline_min1",
    "kline_min3",
    "kline_min5",
    "kline_min10",
    "kline_min15",
    "kline_min30",
    "kline_min60",
    "kline_min120",
    "kline_day",
    "kline_week",
    "kline_month",
    "kline_season",
    "kline_year",
]


async def find_backup_tables(session, timestamp: str = None) -> dict:
    """查找备份表.

    Args:
        session: 数据库会话
        timestamp: 可选的时间戳过滤

    Returns:
        原表名到备份表名的映射字典
    """
    if timestamp:
        pattern = f"%_backup_{timestamp}"
    else:
        pattern = "%_backup_%"

    result = await session.execute(
        text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name LIKE :pattern
        """),
        {"pattern": pattern},
    )

    backups = {}
    for row in result.fetchall():
        backup_name = row[0]
        # 从备份表名解析原表名 (e.g., kline_day_backup_20240423_120000 -> kline_day)
        if "_backup_" in backup_name:
            original = backup_name.split("_backup_")[0]
            backups[original] = backup_name

    return backups


async def get_table_row_count(session, table_name: str) -> int:
    """获取表的行数."""
    result = await session.execute(text(f'SELECT count(*) FROM "{table_name}"'))
    count = result.scalar()
    return count or 0


async def rollback_table(session, table_name: str, backup_name: str) -> dict:
    """回滚单个表.

    Args:
        session: 数据库会话
        table_name: 原表名
        backup_name: 备份表名

    Returns:
        回滚结果字典
    """
    logger.info(f"回滚表: {table_name} <- {backup_name}")
    result = {
        "table": table_name,
        "backup": backup_name,
        "backup_count": 0,
        "restored_count": 0,
        "success": False,
    }

    try:
        # 1. 获取备份表行数
        result["backup_count"] = await get_table_row_count(session, backup_name)
        logger.info(f"备份表 {backup_name} 行数: {result['backup_count']}")

        # 2. 删除当前表（如果存在）
        await session.execute(
            text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
        )
        await session.commit()
        logger.info(f"删除当前表: {table_name}")

        # 3. 重命名备份表为原表名
        # 备份表保留了原始结构（包含 id 列），重命名后即为原始表
        await session.execute(
            text(f'ALTER TABLE "{backup_name}" RENAME TO "{table_name}"')
        )
        await session.commit()
        logger.info(f"重命名备份表: {backup_name} -> {table_name}")

        # 4. 验证行数
        result["restored_count"] = await get_table_row_count(session, table_name)
        if result["backup_count"] != result["restored_count"]:
            logger.warning(
                f"行数不一致: 备份 {result['backup_count']}, "
                f"恢复后 {result['restored_count']}"
            )

        # 5. 重建 hypertable
        # 备份表是普通表，需要重新转换为 hypertable
        hypertable_created = await create_hypertable(
            session, table_name, time_column="trade_time"
        )
        if not hypertable_created:
            logger.warning(f"重建 hypertable 可能失败: {table_name}")

        result["success"] = True
        logger.info(f"表 {table_name} 回滚成功")

    except Exception as e:
        logger.error(f"回滚表 {table_name} 失败: {e}")
        result["error"] = str(e)
        await session.rollback()

    return result


async def rollback_all(
    timestamp: str = None, tables: list = None
) -> dict:
    """回滚所有或指定表.

    Args:
        timestamp: 可选的备份时间戳过滤
        tables: 可选的指定表名列表

    Returns:
        表名到回滚结果的字典
    """
    async with async_db_manager.session() as session:
        backups = await find_backup_tables(session, timestamp)

        if not backups:
            logger.warning("未找到备份表")
            return {}

        results = {}

        if tables:
            # 仅回滚指定表
            for table_name in tables:
                if table_name in backups:
                    result = await rollback_table(
                        session, table_name, backups[table_name]
                    )
                    results[table_name] = result
                else:
                    logger.warning(f"未找到备份表: {table_name}")
                    results[table_name] = {
                        "table": table_name,
                        "success": False,
                        "error": "未找到备份表",
                    }
        else:
            # 回滚所有找到备份的表
            for table_name, backup_name in backups.items():
                result = await rollback_table(session, table_name, backup_name)
                results[table_name] = result

        return results


def main():
    parser = argparse.ArgumentParser(description="K 线表主键迁移回滚脚本")
    parser.add_argument(
        "--timestamp",
        help="备份时间戳 (YYYYMMDD_HHMMSS)",
    )
    parser.add_argument(
        "--table",
        action="append",
        help="指定要回滚的表（可多次使用）",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="回滚所有找到备份的表",
    )
    args = parser.parse_args()

    if not args.all and not args.table:
        parser.error("请指定 --all 或 --table")

    tables = args.table if args.table else None
    results = asyncio.run(
        rollback_all(timestamp=args.timestamp, tables=tables)
    )

    # 打印结果
    print("\n" + "=" * 60)
    print("回滚结果汇总")
    print("=" * 60)
    success_count = 0
    for table_name, result in results.items():
        status = "成功" if result.get("success") else "失败"
        error = f" - 错误: {result.get('error', '')}" if result.get("error") else ""
        print(
            f"  {table_name}: {status}"
            f" (备份: {result.get('backup_count', 0)}, "
            f"恢复: {result.get('restored_count', 0)})"
            f"{error}"
        )
        if result.get("success"):
            success_count += 1

    print("=" * 60)
    print(f"回滚完成: {success_count}/{len(results)} 个表成功")

    # 如果有失败，返回非零退出码
    if any(not r.get("success") for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
