"""TimescaleDB 特定功能.

提供 TimescaleDB 特有的功能，如 hypertable 创建和管理.
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def create_hypertable(
    session: AsyncSession, table_name: str, time_column: str = "trade_time"
) -> bool:
    """将普通表转换为 TimescaleDB hypertable.

    Args:
        session: 异步数据库会话
        table_name: 表名
        time_column: 时间列名，默认为 "trade_time"

    Returns:
        bool: 是否成功创建 hypertable
    """
    try:
        # 检查 TimescaleDB 扩展是否存在
        result = await session.execute(
            text(
                "SELECT installed_version FROM pg_available_extensions WHERE name = 'timescaledb';"
            )
        )
        if not result.fetchone():
            logger.warning(f"TimescaleDB 扩展未安装，跳过 hypertable 创建: {table_name}")
            return False

        # 检查表是否存在
        result = await session.execute(
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
        result = await session.execute(
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

        # 创建 hypertable(nocodb 形态中文表名,双引号括起)
        hypertable_sql = (
            f"SELECT create_hypertable(\"{table_name}\", '{time_column}', if_not_exists => true);"
        )
        await session.execute(text(hypertable_sql))
        await session.commit()

        logger.info(f"成功创建 hypertable: {table_name}")
        return True

    except Exception as e:
        logger.error(f"创建 hypertable 失败 {table_name}: {e}")
        await session.rollback()
        return False

async def apply_retention_policy(
    session: AsyncSession, table_name: str, retention_days: int
) -> bool:
    """为 hypertable 设置滚动 retention(2026-10-22 引入,分钟线 22 天滚动).

    add_retention_policy 幂等(重复调用更新 interval)。定时在 minute cover
    job 内调用,interval 取 config minute_retention_days。
    """
    try:
        await session.execute(
            text("SELECT add_retention_policy(:tbl, INTERVAL '1 day' * :days, if_not_exists => TRUE)"),
            {"tbl": table_name, "days": retention_days},
        )
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"设置 retention 失败 {table_name}: {e}")
        await session.rollback()
        return False

async def create_kline_hypertables(session: AsyncSession) -> None:
    """为 20 张日度/时间序列表创建 hypertable(nocodb 形态中文表名,2026-08-26 回迁).

    chunk 间隔与旧库一致:K线 13 表 7d;backward_factor 360d;30d 组(akshare/
    大宗/行业日行情/龙虎榜/两融明细/两融汇总)30d。
    """
    from galaxy_core.shared_kernel.nocodb_schema import TABLE_NAMES

    def t(canonical: str) -> str:
        return TABLE_NAMES[canonical]

    # K线表 13 张(7d)
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
        await create_hypertable(session, t(table_name))

    # backward_factor: 日频参考数据，按年分区(旧库 360d)
    await create_hypertable(session, t("backward_factor"), time_column="trade_date")

    # industry_daily: 行业指数日行情，按 trade_date 分区
    await create_hypertable(session, t("industry_daily"), time_column="trade_date")

    # === 30d 组(资金流 5 表 + akshare) ===
    await create_hypertable(session, t("akshare_sector_fund_flow_daily"), time_column="trade_date")
    await create_hypertable(session, t("long_hu_bang"), time_column="trade_date")
    await create_hypertable(session, t("block_trading"), time_column="trade_date")
    await create_hypertable(session, t("margin_summary_daily"), time_column="trade_date")
    await create_hypertable(session, t("margin_detail_daily"), time_column="trade_date")
