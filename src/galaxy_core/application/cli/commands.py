"""CLI 命令入口."""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from time import struct_time

from alembic.config import Config
from sqlalchemy import text

from alembic import command as alembic_command
from galaxy_core.application.calendar.command import (
    create_calendar_parser,
    handle_calendar_command_async,
)
from galaxy_core.application.financial.command import handle_financial_command_async
from galaxy_core.application.financial.parser import create_financial_parser
from galaxy_core.application.fundflow.command import handle_fundflow_command_async
from galaxy_core.application.fundflow.parser import create_fundflow_parser
from galaxy_core.application.index.command import handle_index_command_async
from galaxy_core.application.index.parser import create_index_parser
from galaxy_core.application.kline.command import handle_kline_command_async
from galaxy_core.application.kline.parser import create_kline_parser
from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.database.core.timescale import create_kline_hypertables
from galaxy_core.di.container import create_container
from galaxy_core.shared_kernel.utils.config_loader import get_section
from galaxy_core.shared_kernel.utils.constants import CST, now_cst


# 配置日志
def setup_logging():
    """根据配置文件设置日志"""
    log_config = get_section("logging")

    # 获取日志配置
    log_level = log_config.get("level", "INFO").upper()

    # 检查是否启用分离日志文件功能
    enable_separate_logs = log_config.get("enable_separate_log_files", False)

    if enable_separate_logs:
        # 按日期时间生成日志文件路径。文件名时间用北京时间(AGENTS.md 2026-06-25),
        # 而非服务器本地时间(UTC)——审计按文件名时间判定 CLI 实际执行时刻。
        log_file_pattern = log_config.get("log_file_pattern", "./logs/{date}/{time}.log")
        current_time = now_cst()
        date_str = current_time.strftime("%Y%m%d")
        time_str = current_time.strftime("%H%M%S")

        # 替换路径中的占位符
        log_file_path = log_file_pattern.format(date=date_str, time=time_str)
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
    # asctime 用北京时间:默认 converter=time.localtime 返回服务器本地时间(UTC),
    # 改为按 CST 转换,使日志行内时间戳与文件名时间一致(均为北京时间)。

    def _cst_converter(seconds: float | None) -> struct_time:
        # seconds=None 时回退到当前时刻(typeshed 签名允许 None)
        ts = seconds if seconds is not None else datetime.now(CST).timestamp()
        return datetime.fromtimestamp(ts, CST).timetuple()

    formatter.converter = _cst_converter

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


if "pytest" not in sys.modules:
    setup_logging()
logger = logging.getLogger(__name__)


async def async_main() -> int:
    """异步 CLI 主入口.

    Per ASYNC-05: 使用 asyncio.run() 在 main() 中驱动此异步函数。
    Per COMPAT-01: 保持相同的参数解析和命令分发逻辑。
    """
    parser = argparse.ArgumentParser(
        prog="galaxy-core",
        description="银河证券AmazingData数据接入工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 注册各命令解析器
    create_kline_parser(subparsers)
    create_calendar_parser(subparsers)
    create_financial_parser(subparsers)
    create_index_parser(subparsers)
    create_fundflow_parser(subparsers)

    # scheduler 命令解析器
    scheduler_parser = subparsers.add_parser(
        "scheduler",
        help="启动自动同步调度器",
    )
    scheduler_parser.add_argument(
        "--env",
        type=str,
        default="",
        help="配置环境名称（dev/prod），默认使用 GALAXY_CONFIG_ENV 或 settings.toml",
    )
    scheduler_parser.add_argument(
        "--replace",
        action="store_true",
        help="如果已有调度器在运行，强制终止旧实例后启动新实例",
    )

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
        # 从 DI 容器获取 KlineDataService、AsyncDatabaseManager 和 ReferenceProvider
        container = create_container()
        kline_service = container.kline_service()
        db_manager_inst = container.db_manager()
        reference_provider_inst = container.reference_provider()
        return await handle_kline_command_async(
            args,
            kline_service=kline_service,
            async_db_manager=db_manager_inst,
            reference_provider=reference_provider_inst,
        )
    elif args.command == "calendar":
        # 从 DI 容器获取 CalendarDataService
        container = create_container()
        calendar_service = container.calendar_service()
        return await handle_calendar_command_async(args, calendar_service=calendar_service)
    elif args.command == "financial":
        # 从 DI 容器获取 FinancialDataService
        container = create_container()
        financial_service = container.financial_service()
        return await handle_financial_command_async(args, financial_service=financial_service)
    elif args.command == "index":
        # 从 DI 容器获取指数同步 job（Phase 01：手动触发交易所/行业指数同步）
        container = create_container()
        return await handle_index_command_async(
            args,
            exchange_index_job=container.exchange_index_job(),
            industry_index_job=container.industry_index_job(),
        )
    elif args.command == "fundflow":
        # 从 DI 容器获取资金流向同步 job（Phase 02：手动触发 akshare+AmazingData 资金流同步）
        container = create_container()
        return await handle_fundflow_command_async(
            args,
            fundflow_job=container.fundflow_job(),
        )
    elif args.command == "scheduler":
        from galaxy_core.application.scheduler.scheduler import run_scheduler

        return await run_scheduler(replace=args.replace)
    elif args.command == "init-db":
        # 从 DI 容器获取 AsyncDatabaseManager
        container = create_container()
        db_manager = container.db_manager()
        return await handle_init_db_command(args, db_manager=db_manager)
    else:
        parser.print_help()
        return 1


async def handle_init_db_command(
    args: argparse.Namespace, db_manager: AsyncDatabaseManager | None = None
) -> int:
    """处理 init-db 命令.

    1. 运行 alembic upgrade head 创建/迁移表结构
    2. 创建 TimescaleDB hypertables
    3. 支持 --recreate 标志删除并重建

    Args:
        args: CLI 参数
        db_manager: AsyncDatabaseManager 实例（DI 注入）
    """
    logger.info("开始初始化数据库...")

    # 定位 alembic.ini（基于项目根目录）
    project_root = Path(__file__).resolve().parents[4]
    alembic_ini = project_root / "alembic.ini"

    if not alembic_ini.exists():
        logger.error(f"找不到 alembic.ini: {alembic_ini}")
        return 1

    # 使用注入的 db_manager 或从 DI 获取
    if db_manager is None:
        container = create_container()
        db_manager = container.db_manager()

    # 初始化异步数据库连接池
    db_manager.initialize()

    if args.recreate:
        logger.warning("正在删除所有数据表...")
        await db_manager.drop_tables()
        logger.info("数据表已删除")

    alembic_cfg = Config(str(alembic_ini))

    # 检测是否需要 stamp（已有表但无 alembic_version）
    async with db_manager.session() as session:
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

    async with db_manager.session() as session:
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
