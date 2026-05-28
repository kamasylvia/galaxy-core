#!/usr/bin/env python3
"""K 线表主键迁移脚本：将自增 id 改为 (symbol, trade_time) 组合主键.

执行流程：
1. 备份每个表到 backup 表
2. 验证备份行数
3. 删除旧表（级联删除 hypertable）
4. 创建新表（使用新模型，组合主键）
5. 从备份恢复数据（排除 id 列）
6. 验证数据行数
7. 重建 hypertable
8. 可选：删除备份表

Usage:
    python scripts/migrate_pk_to_symbol_trade_time.py [--dry-run] [--keep-backup]
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime

from sqlalchemy import text

from galaxy_db_sync.database.core.async_connection import async_db_manager
from galaxy_db_sync.database.core.timescale import create_hypertable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 13 个 K 线表，按数据量从小到大排序（小表先迁移，减少长时间锁定风险）
KLINE_TABLES = [
    "kline_year",      # 数据量最小，优先迁移
    "kline_season",
    "kline_month",
    "kline_week",
    "kline_day",
    "kline_min120",
    "kline_min60",
    "kline_min30",
    "kline_min15",
    "kline_min10",
    "kline_min5",
    "kline_min3",
    "kline_min1",      # 数据量最大，最后迁移
]


async def get_table_row_count(session, table_name: str) -> int:
    """获取表的行数."""
    result = await session.execute(text(f'SELECT count(*) FROM "{table_name}"'))
    count = result.scalar()
    return count or 0


async def table_exists(session, table_name: str) -> bool:
    """检查表是否存在."""
    result = await session.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table_name
            );
        """),
        {"table_name": table_name},
    )
    return bool(result.scalar())


async def create_backup_table(session, table_name: str, backup_name: str) -> int:
    """创建备份表并返回行数."""
    logger.info(f"创建备份表: {backup_name}")
    await session.execute(
        text(f'CREATE TABLE "{backup_name}" AS SELECT * FROM "{table_name}"')
    )
    await session.commit()
    count = await get_table_row_count(session, backup_name)
    logger.info(f"备份表 {backup_name} 创建完成，行数: {count}")
    return count


async def drop_old_table(session, table_name: str) -> None:
    """删除旧表（级联删除 hypertable）."""
    logger.info(f"删除旧表: {table_name}")
    await session.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
    await session.commit()


async def create_new_table(session, table_name: str) -> None:
    """创建新表（组合主键，无 id 列）."""
    logger.info(f"创建新表: {table_name}")
    create_sql = f"""
    CREATE TABLE "{table_name}" (
        symbol VARCHAR(20) NOT NULL,
        trade_time TIMESTAMP NOT NULL,
        open DOUBLE PRECISION,
        high DOUBLE PRECISION,
        low DOUBLE PRECISION,
        close DOUBLE PRECISION,
        volume BIGINT,
        amount DOUBLE PRECISION,
        security_type VARCHAR(20),
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (symbol, trade_time)
    );
    """
    await session.execute(text(create_sql))
    await session.commit()


async def restore_data(session, table_name: str, backup_name: str) -> int:
    """从备份表恢复数据（排除 id 列）."""
    logger.info(f"从备份恢复数据: {backup_name} -> {table_name}")
    insert_sql = f"""
    INSERT INTO "{table_name}" (
        symbol, trade_time, open, high, low, close,
        volume, amount, security_type, created_at, updated_at
    )
    SELECT
        symbol, trade_time, open, high, low, close,
        volume, amount, security_type, created_at, updated_at
    FROM "{backup_name}";
    """
    result = await session.execute(text(insert_sql))
    await session.commit()
    count = result.rowcount or 0
    logger.info(f"恢复完成，插入行数: {count}")
    return count


async def create_hypertable_for_table(session, table_name: str) -> bool:
    """为新表创建 hypertable."""
    logger.info(f"创建 hypertable: {table_name}")
    return await create_hypertable(session, table_name, time_column="trade_time")


async def migrate_table(
    session, table_name: str, timestamp: str, dry_run: bool = False
) -> dict:
    """迁移单个表.

    Args:
        session: 数据库会话
        table_name: 表名
        timestamp: 备份时间戳
        dry_run: 是否仅模拟执行

    Returns:
        迁移结果字典
    """
    backup_name = f"{table_name}_backup_{timestamp}"
    result = {
        "table": table_name,
        "backup": backup_name,
        "original_count": 0,
        "backup_count": 0,
        "restored_count": 0,
        "success": False,
    }

    try:
        # 检查表是否存在
        if not await table_exists(session, table_name):
            logger.warning(f"表不存在，跳过: {table_name}")
            result["success"] = True
            return result

        # 1. 获取原始表行数
        result["original_count"] = await get_table_row_count(session, table_name)
        logger.info(f"表 {table_name} 原始行数: {result['original_count']}")

        if dry_run:
            logger.info(f"[DRY RUN] 将迁移表: {table_name}")
            result["success"] = True
            return result

        # 2. 创建备份表
        result["backup_count"] = await create_backup_table(
            session, table_name, backup_name
        )

        # 3. 验证备份行数
        if result["original_count"] != result["backup_count"]:
            raise ValueError(
                f"备份行数不匹配: 原始 {result['original_count']}, "
                f"备份 {result['backup_count']}"
            )

        # 4. 删除旧表
        await drop_old_table(session, table_name)

        # 5. 创建新表
        await create_new_table(session, table_name)

        # 6. 恢复数据
        result["restored_count"] = await restore_data(
            session, table_name, backup_name
        )

        # 7. 验证数据行数
        if result["original_count"] != result["restored_count"]:
            raise ValueError(
                f"恢复行数不匹配: 原始 {result['original_count']}, "
                f"恢复 {result['restored_count']}"
            )

        # 8. 创建 hypertable
        hypertable_created = await create_hypertable_for_table(session, table_name)
        if not hypertable_created:
            logger.warning(f"创建 hypertable 可能失败: {table_name}")

        result["success"] = True
        logger.info(f"表 {table_name} 迁移成功")

    except Exception as e:
        logger.error(f"表 {table_name} 迁移失败: {e}")
        result["error"] = str(e)
        raise

    return result


async def drop_backup_tables(session, timestamp: str) -> list:
    """删除指定时间戳的所有备份表.

    Args:
        session: 数据库会话
        timestamp: 备份时间戳

    Returns:
        删除的备份表名列表
    """
    pattern = f"%_backup_{timestamp}"
    result = await session.execute(
        text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name LIKE :pattern
        """),
        {"pattern": pattern},
    )

    dropped = []
    for row in result.fetchall():
        backup_name = row[0]
        logger.info(f"删除备份表: {backup_name}")
        await session.execute(text(f'DROP TABLE IF EXISTS "{backup_name}" CASCADE'))
        dropped.append(backup_name)

    await session.commit()
    return dropped


async def migrate_all_tables(
    dry_run: bool = False, keep_backup: bool = False
) -> list:
    """迁移所有 K 线表.

    Args:
        dry_run: 是否仅模拟执行
        keep_backup: 是否保留备份表

    Returns:
        每个表的迁移结果列表
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = []

    async with async_db_manager.session() as session:
        for table_name in KLINE_TABLES:
            try:
                result = await migrate_table(session, table_name, timestamp, dry_run)
                results.append(result)
            except Exception as e:
                logger.error(f"迁移中断: {e}")
                break

    # 如果不保留备份且不是 dry-run，删除备份表
    if not dry_run and not keep_backup:
        logger.info("清理备份表...")
        async with async_db_manager.session() as session:
            dropped = await drop_backup_tables(session, timestamp)
            logger.info(f"已删除 {len(dropped)} 个备份表")

    # 汇总结果
    success_count = sum(1 for r in results if r.get("success"))
    total_count = len(KLINE_TABLES)
    logger.info(f"迁移完成: {success_count}/{total_count} 个表成功")

    # 打印详细结果
    print("\n" + "=" * 60)
    print("迁移结果汇总")
    print("=" * 60)
    for r in results:
        status = "成功" if r.get("success") else "失败"
        error = f" - 错误: {r.get('error', '')}" if r.get("error") else ""
        print(
            f"  {r['table']}: {status}"
            f" (原始: {r['original_count']}, 恢复: {r.get('restored_count', 0)})"
            f"{error}"
        )
    print("=" * 60)

    return results


def main():
    parser = argparse.ArgumentParser(description="K 线表主键迁移脚本")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印将要执行的操作，不实际执行",
    )
    parser.add_argument(
        "--keep-backup",
        action="store_true",
        help="保留备份表（用于回滚）",
    )
    args = parser.parse_args()

    results = asyncio.run(
        migrate_all_tables(dry_run=args.dry_run, keep_backup=args.keep_backup)
    )

    # 如果有失败，返回非零退出码
    if any(not r.get("success") for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
