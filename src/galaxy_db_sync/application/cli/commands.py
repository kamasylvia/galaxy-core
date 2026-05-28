"""CLI 命令入口."""

import argparse
import asyncio
import logging
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

from galaxy_db_sync.application.calendar.command import (
    create_calendar_parser,
    handle_calendar_command,
)
from galaxy_db_sync.application.kline.command import handle_kline_command_async
from galaxy_db_sync.application.kline.parser import create_kline_parser
from galaxy_db_sync.database.core.async_connection import async_db_manager
from galaxy_db_sync.database.core.timescale import create_kline_hypertables
from galaxy_db_sync.shared_kernel.utils.config_loader import get_section
from alembic.config import Config
from alembic import command as alembic_command
from sqlalchemy import text


def _cleanup_old_log_directories(log_base_path: Path, backup_count: int, current_date: datetime):
    """清理超过 backup_count 天数的旧日志目录.

    Args:
        log_base_path: 日志根目录 (如 ./logs/)
        backup_count: 保留的日志天数
        current_date: 当前日期，用于计算截止日期
    """
    if not log_base_path.exists():
        return

    # 计算截止日期
    cutoff_date = current_date - timedelta(days=backup_count)

    # 找到所有日期子目录（格式 YYYYMMDD）
    try:
        date_dirs = []
        for item in log_base_path.iterdir():
            if item.is_dir() and len(item.name) == 8 and item.name.isdigit():
                try:
                    dir_date = datetime.strptime(item.name, "%Y%m%d")
                    date_dirs.append((item, dir_date))
                except ValueError:
                    continue  # 不是有效日期格式，跳过

        # 按日期排序
        date_dirs.sort(key=lambda x: x[1])

        # 删除超过 cutoff_date 的目录
        deleted_count = 0
        for dir_path, dir_date in date_dirs:
            if dir_date < cutoff_date:
                try:
                    shutil.rmtree(dir_path)
                    deleted_count += 1
                except Exception:
                    pass  # 删除失败，忽略

        if deleted_count > 0:
            # 使用临时 logger（因为主 logger 可能还没初始化）
            print(f"清理了 {deleted_count} 个旧日志目录（保留 {backup_count} 天）")
    except Exception as e:
        print(f"清理日志目录时出错: {e}")


# 配置日志
def setup_logging():
    """根据配置文件设置日志"""
    log_config = get_section("logging")

    # 获取日志配置
    log_level = log_config.get("level", "INFO").upper()

    # 检查是否启用分离日志文件功能
    enable_separate_logs = log_config.get("enable_separate_log_files", False)

    if enable_separate_logs:
        # 按日期时间生成日志文件路径
        log_file_pattern = log_config.get("log_file_pattern", "./logs/{date}/{time}.log")
        backup_count = log_config.get("backup_count", 5)  # 保留天数
        current_time = datetime.now()
        date_str = current_time.strftime("%Y%m%d")
        time_str = current_time.strftime("%H%M%S")

        # 替换路径中的占位符
        log_file_path = log_file_pattern.format(date=date_str, time=time_str)

        # 清理旧日志目录
        log_file = Path(log_file_path)
        log_base_path = log_file.parent.parent  # logs/{date}/{time}.log -> logs/
        _cleanup_old_log_directories(log_base_path, backup_count, current_time)
    else:
        # 传统模式
        log_file_path = log_config.get("file_path", "./data/logs/app.log")
        max_size = log_config.get("max_size", "100MB")
        backup_count = log_config.get("backup_count", 5)

        # 解析最大文件大小（简单处理，只支持MB单位）
        max_bytes = 100 * 1024 * 1024  # 默认100MB
        if "MB" in max_size.upper():
            try:
                size_value = int(max_size.upper().replace("MB", "").strip())
                max_bytes = size_value * 1024 * 1024
            except ValueError:
                pass  # 使用默认值

        # 确保日志目录存在
        log_file = Path(log_file_path)

        # 检查log_file_path是否是一个目录
        if log_file.is_dir():
            # 如果是目录，则添加默认文件名
            log_file = log_file / "app.log"
            log_file_path = str(log_file)

    # 确保日志目录存在
    log_file = Path(log_file_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))

    # 清除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 创建格式器
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # 根据配置选择处理器类型
    if enable_separate_logs:
        # 使用普通文件处理器（单次运行写入单个文件）
        from logging import FileHandler

        file_handler = FileHandler(log_file_path, encoding="utf-8")
    else:
        # 使用轮转文件处理器（传统的单文件轮转）
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )

    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, log_level))

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level))

    # 添加处理器到根日志记录器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


setup_logging()
logger = logging.getLogger(__name__)


async def async_main() -> int:
    """异步 CLI 主入口.

    Per ASYNC-05: 使用 asyncio.run() 在 main() 中驱动此异步函数。
    Per COMPAT-01: 保持相同的参数解析和命令分发逻辑。
    """
    parser = argparse.ArgumentParser(
        prog="galaxy-db-sync",
        description="银河证券AmazingData数据接入工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 注册各命令解析器
    create_kline_parser(subparsers)
    create_calendar_parser(subparsers)

    # init-db 命令解析器
    init_db_parser = subparsers.add_parser(
        "init-db",
        help="初始化数据库（运行 Alembic 迁移并创建 hypertables）",
    )
    init_db_parser.add_argument(
        "--recreate",
        action="store_true",
        help="删除并重新创建所有表（危险！会丢失数据）",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    print(f"执行命令: {args.command}")
    print(f"参数: {args}")

    # 执行对应的命令
    if args.command == "kline":
        return await handle_kline_command_async(args)
    elif args.command == "calendar":
        # calendar 命令仍为同步，使用 asyncio.to_thread 包装
        return await asyncio.to_thread(handle_calendar_command, args)
    elif args.command == "init-db":
        return await handle_init_db_command(args)
    else:
        parser.print_help()
        return 1


async def handle_init_db_command(args: argparse.Namespace) -> int:
    """处理 init-db 命令.

    1. 运行 alembic upgrade head 创建/迁移表结构
    2. 创建 TimescaleDB hypertables
    3. 支持 --recreate 标志删除并重建
    """
    logger.info("开始初始化数据库...")

    # 定位 alembic.ini（基于项目根目录）
    project_root = Path(__file__).resolve().parents[4]
    alembic_ini = project_root / "alembic.ini"

    if not alembic_ini.exists():
        logger.error(f"找不到 alembic.ini: {alembic_ini}")
        return 1

    # 初始化异步数据库连接池
    async_db_manager.initialize()

    if args.recreate:
        logger.warning("正在删除所有数据表...")
        await async_db_manager.drop_tables()
        logger.info("数据表已删除")

    alembic_cfg = Config(str(alembic_ini))

    # 检测是否需要 stamp（已有表但无 alembic_version）
    async with async_db_manager.session() as session:
        result = await session.execute(
            text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alembic_version')"
            )
        )
        has_alembic_version = result.scalar()

        if not has_alembic_version:
            result = await session.execute(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'trading_calendar')"
                )
            )
            has_tables = result.scalar()

            if has_tables:
                logger.info("检测到已有数据表但未记录 Alembic 版本，正在标记当前版本...")
                alembic_command.stamp(alembic_cfg, "head")
                await create_kline_hypertables(session)
                logger.info("数据库初始化完成！")
                return 0

    # 正常迁移路径
    logger.info("运行数据库迁移...")
    alembic_command.upgrade(alembic_cfg, "head")
    logger.info("数据库迁移完成")

    async with async_db_manager.session() as session:
        await create_kline_hypertables(session)
    logger.info("TimescaleDB hypertables 创建完成")

    logger.info("数据库初始化完成！")
    return 0


def main() -> int:
    """CLI 入口点 - 使用 asyncio.run() 包装 async_main.

    Per ASYNC-05: CLI 使用 asyncio.run() 驱动异步命令处理。
    """
    try:
        return asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n操作已取消", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
