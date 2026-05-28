"""TimescaleDB 特定功能.

提供 TimescaleDB 特有的功能，如 hypertable 创建和管理.
"""

import logging
from typing import List

from sqlalchemy import text
from sqlalchemy.orm import Session

from galaxy_db_bridge.database.core.connection import db_manager

logger = logging.getLogger(__name__)


def create_hypertable(
    session: Session, table_name: str, time_column: str = "trade_time"
) -> bool:
    """将普通表转换为 TimescaleDB hypertable.

    Args:
        session: 数据库会话
        table_name: 表名
        time_column: 时间列名，默认为 "trade_time"

    Returns:
        bool: 是否成功创建 hypertable
    """
    try:
        # 检查 TimescaleDB 扩展是否存在
        result = session.execute(
            text(
                "SELECT installed_version FROM pg_available_extensions WHERE name = 'timescaledb';"
            )
        )
        if not result.fetchone():
            logger.warning(
                f"TimescaleDB 扩展未安装，跳过 hypertable 创建: {table_name}"
            )
            return False

        # 检查表是否存在
        result = session.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = :table_name
                );
            """),
            {"table_name": table_name},
        )
        table_exists = result.scalar()

        if not table_exists:
            logger.warning(f"表不存在，无法创建 hypertable: {table_name}")
            return False

        # 检查是否已经是 hypertable
        result = session.execute(
            text("""
                SELECT hypertable_name
                FROM timescaledb_information.hypertables
                WHERE hypertable_name = :table_name;
            """),
            {"table_name": table_name},
        )
        is_hypertable = result.scalar()

        if is_hypertable:
            logger.info(f"表已经是 hypertable: {table_name}")
            return True

        # 创建 hypertable
        hypertable_sql = f"""
            SELECT create_hypertable(
                '{table_name}',
                '{time_column}',
                if_not_exists => true
            );
        """
        session.execute(text(hypertable_sql))
        session.commit()

        logger.info(f"成功创建 hypertable: {table_name}")
        return True

    except Exception as e:
        logger.error(f"创建 hypertable 失败 {table_name}: {e}")
        session.rollback()
        return False


def create_kline_hypertables() -> None:
    """为所有 K 线表创建 hypertable."""
    with db_manager.session() as session:
        # K线表名列表
        kline_tables = [
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

        for table_name in kline_tables:
            create_hypertable(session, table_name)
