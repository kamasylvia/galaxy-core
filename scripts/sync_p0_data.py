#!/usr/bin/env python
"""P0 基础数据同步脚本（异步版本）.

同步以下数据到 PostgreSQL:
1. stock_basic - 证券基础信息 (低频次更新)
2. stock_status - 历史证券状态 (停牌/ST/涨跌停/除权除息, 日频)
3. backward_factor - 后复权因子 (日频)

架构约束:
- 所有数据库交互使用 async_db_manager + AsyncSession (项目强制规范)
- API 调用(SDK 同步)通过 asyncio.to_thread 包装
- 配置从 config/settings.toml 读取
- 日志写入 logs/ 目录（项目约定）

数据来源: AmazingData API
"""

import asyncio
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

# 添加 src 到路径
SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if SRC_PATH.exists():
    sys.path.insert(0, str(SRC_PATH))

# 显式加载项目根目录的 .env
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

# 修正 PROJECT_ROOT_PATH 指向当前项目（.env 中可能指向旧路径）
PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ["PROJECT_ROOT_PATH"] = str(PROJECT_ROOT)

from galaxy_db_sync.amazing_data.api.client import AmazingDataClient
from galaxy_db_sync.database.core.async_connection import (
    AsyncDatabaseManager,
    async_db_manager,
)
from galaxy_db_sync.database.models import BackwardFactor, StockBasic, StockStatus
from galaxy_db_sync.shared_kernel.utils.config_loader import get_config, get_section

# =============================================================================
# 日志配置（遵循项目 settings.toml 约定）
# =============================================================================
log_config = get_section("logging")
log_level = log_config.get("level", "INFO").upper()

if log_config.get("enable_separate_log_files", False):
    pattern = log_config.get("log_file_pattern", "./logs/{date}/{time}.log")
    date_str = datetime.now().strftime("%Y%m%d")
    time_str = datetime.now().strftime("%H%M%S")
    log_file_path = pattern.replace("{date}", date_str).replace("{time}", time_str)
else:
    log_file_path = (
        log_config.get("file_path", "./logs/")
        + f"sync-p0-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    )

log_file = Path(log_file_path)
log_file.parent.mkdir(parents=True, exist_ok=True)

root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, log_level))
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# 文件 handler
file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
file_handler.setFormatter(formatter)
file_handler.setLevel(getattr(logging, log_level))
root_logger.addHandler(file_handler)

# 控制台 handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(getattr(logging, log_level))
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)

# =============================================================================
# 配置读取（来自 config/settings.toml）
# =============================================================================
# SDK 文档要求 local_path 为绝对路径
CACHE_DIR: str = str(Path(get_config("amazing_data", "local_path", "./data/local_cache/")).resolve())
BATCH_SIZE: int = get_config("sync", "batch_size", 200)

# 确保缓存目录存在
Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)


# =============================================================================
# 数据库初始化（异步）
# =============================================================================
async def init_db() -> AsyncDatabaseManager:
    """初始化异步数据库连接并创建表."""
    async_db_manager.initialize(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "quant_db"),
        user=os.getenv("DB_USER", "quant_user"),
        password=os.getenv("DB_PASSWORD", ""),
    )
    await async_db_manager.create_tables()
    return async_db_manager


# =============================================================================
# API 客户端初始化（同步 SDK，通过 to_thread 包装）
# =============================================================================
def _init_api_sync() -> AmazingDataClient:
    """同步初始化 API 客户端."""
    client = AmazingDataClient()
    client.initialize(
        username=os.getenv("GALAXY_USERNAME"),
        password=os.getenv("GALAXY_PASSWORD"),
        host=os.getenv("GALAXY_HOST"),
        port=int(os.getenv("GALAXY_PORT", "8600")),
    )
    return client


async def init_api() -> AmazingDataClient:
    """异步初始化 API 客户端（包装同步 SDK）."""
    return await asyncio.to_thread(_init_api_sync)


async def api_logout(client: AmazingDataClient) -> None:
    """异步登出 API."""
    await asyncio.to_thread(client.logout)


# =============================================================================
# sync_stock_basic
# =============================================================================
async def sync_stock_basic(client: AmazingDataClient, db: AsyncDatabaseManager) -> int:
    """同步证券基础信息（异步数据库写入）."""
    logger.info("=" * 50)
    logger.info("[1/3] 同步证券基础信息 (stock_basic)")
    logger.info("=" * 50)

    # API 调用: 获取股票列表（get_stock_list 内部调用 get_code_info，index 为证券代码）
    stock_df = await asyncio.to_thread(client.get_stock_list, "EXTRA_STOCK_A")
    codes = stock_df.index.tolist()
    logger.info(f"当前 A 股数量: {len(codes)}")

    all_records = []
    for i in range(0, len(codes), BATCH_SIZE):
        batch = codes[i : i + BATCH_SIZE]
        logger.info(f"  获取基础信息: {i + 1} - {min(i + BATCH_SIZE, len(codes))}")
        df = await asyncio.to_thread(client.get_stock_basic, batch)
        if df is None or df.empty:
            continue

        for _, row in df.iterrows():
            code = row.get("MARKET_CODE") or row.get("code")
            if not code:
                continue

            record = {
                "symbol": code,
                "security_name": row.get("SECURITY_NAME"),
                "comp_name": row.get("COMP_NAME"),
                "pinyin": row.get("PINYIN"),
                "list_date": _parse_date(row.get("LISTDATE")),
                "delist_date": _parse_date(row.get("DELISTDATE")),
                "security_type": "EXTRA_STOCK_A",
            }
            all_records.append(record)

    logger.info(f"共获取 {len(all_records)} 条基础信息记录")
    if not all_records:
        return 0

    saved = await _upsert_stock_basic(db, all_records)
    logger.info(f"保存/更新 stock_basic 记录: {saved}")
    return saved


# =============================================================================
# sync_stock_status
# =============================================================================
async def sync_stock_status(
    client: AmazingDataClient, db: AsyncDatabaseManager, codes: list[str]
) -> int:
    """同步历史证券状态（异步数据库写入）."""
    logger.info("=" * 50)
    logger.info("[2/3] 同步历史证券状态 (stock_status)")
    logger.info("=" * 50)

    all_records = []
    total_batches = (len(codes) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(codes), BATCH_SIZE):
        batch = codes[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        logger.info(
            f"  获取证券状态: batch {batch_num}/{total_batches} ({len(batch)} 只)"
        )

        try:
            result = await asyncio.to_thread(
                client.get_history_stock_status,
                code_list=batch,
                local_path=CACHE_DIR,
                is_local=False,
            )
        except Exception as e:
            logger.error(f"    批次 {batch_num} 失败: {e}")
            continue

        if not isinstance(result, dict):
            logger.warning(f"    返回类型非 dict: {type(result)}")
            continue

        for code, df in result.items():
            if df is None or df.empty:
                continue
            records = _parse_stock_status_df(code, df)
            all_records.extend(records)

        if batch_num % 5 == 0:
            logger.info(f"  累计记录数: {len(all_records)}")

    logger.info(f"共获取 {len(all_records)} 条状态记录")
    if not all_records:
        return 0

    saved = await _upsert_stock_status(db, all_records)
    logger.info(f"保存/更新 stock_status 记录: {saved}")
    return saved


# =============================================================================
# sync_backward_factor
# =============================================================================
async def sync_backward_factor(
    client: AmazingDataClient, db: AsyncDatabaseManager, codes: list[str]
) -> int:
    """同步后复权因子（异步数据库写入）."""
    logger.info("=" * 50)
    logger.info("[3/3] 同步后复权因子 (backward_factor)")
    logger.info("=" * 50)

    all_records = []
    total_batches = (len(codes) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(codes), BATCH_SIZE):
        batch = codes[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        logger.info(
            f"  获取复权因子: batch {batch_num}/{total_batches} ({len(batch)} 只)"
        )

        try:
            df = await asyncio.to_thread(
                client.get_backward_factor,
                code_list=batch,
                local_path=CACHE_DIR,
                is_local=False,
            )
        except Exception as e:
            logger.error(f"    批次 {batch_num} 失败: {e}")
            continue

        if df is None or df.empty:
            logger.warning(f"    批次 {batch_num} 返回空数据")
            continue

        records = _parse_backward_factor_df(df)
        all_records.extend(records)

        if batch_num % 5 == 0:
            logger.info(f"  累计记录数: {len(all_records)}")

    logger.info(f"共获取 {len(all_records)} 条复权因子记录")
    if not all_records:
        return 0

    saved = await _upsert_backward_factor(db, all_records)
    logger.info(f"保存/更新 backward_factor 记录: {saved}")
    return saved


# =============================================================================
# 数据解析工具函数
# =============================================================================
def _parse_date(value) -> date | None:
    """解析日期值."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)):
        value = str(int(value))
    if isinstance(value, str):
        value = value.strip()
        if len(value) == 8:
            return date(int(value[:4]), int(value[4:6]), int(value[6:]))
        if len(value) == 10 and value[4] == "-":
            return date.fromisoformat(value)
    return None


def _parse_stock_status_df(code: str, df: pd.DataFrame) -> list[dict]:
    """将 stock_status DataFrame 转换为记录列表."""
    records = []
    for _, row in df.iterrows():
        trade_date = _parse_date(row.get("TRADE_DATE"))
        if trade_date is None:
            continue
        records.append(
            {
                "symbol": code,
                "trade_date": trade_date,
                "preclose": _to_float(row.get("PRECLOSE")),
                "high_limited": _to_float(row.get("HIGH_LIMITED")),
                "low_limited": _to_float(row.get("LOW_LIMITED")),
                "is_st": _to_bool(row.get("IS_ST_SEC")),
                "is_susp": _to_bool(row.get("IS_SUSP_SEC")),
                "is_xr": _to_bool(row.get("IS_XR_SEC")),
                "is_wd": _to_bool(row.get("IS_WD_SEC")),
            }
        )
    return records


def _parse_backward_factor_df(df: pd.DataFrame) -> list[dict]:
    """将 backward_factor DataFrame 转换为记录列表.

    DataFrame 格式: index=日期, columns=股票代码
    """
    records = []
    df.index = pd.to_datetime(df.index)
    for trade_dt in df.index:
        trade_date = trade_dt.date()
        for col in df.columns:
            val = df.loc[trade_dt, col]
            if pd.isna(val):
                continue
            records.append(
                {
                    "symbol": col,
                    "trade_date": trade_date,
                    "factor": float(val),
                }
            )
    return records


def _to_float(value) -> float | None:
    """安全转换为 float."""
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _to_bool(value) -> bool:
    """安全转换为 bool."""
    if value is None or pd.isna(value):
        return False
    try:
        return bool(int(value))
    except (ValueError, TypeError):
        return False


# =============================================================================
# 异步 UPSERT 操作
# =============================================================================
async def _upsert_stock_basic(db: AsyncDatabaseManager, records: list[dict]) -> int:
    """异步批量 UPSERT stock_basic 记录."""
    if not records:
        return 0

    batch_size = 3000
    total = 0
    async with db.session() as session:
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            stmt = pg_insert(StockBasic).values(batch)
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=["symbol"],
                set_={
                    "security_name": stmt.excluded.security_name,
                    "comp_name": stmt.excluded.comp_name,
                    "pinyin": stmt.excluded.pinyin,
                    "list_date": stmt.excluded.list_date,
                    "delist_date": stmt.excluded.delist_date,
                    "security_type": stmt.excluded.security_type,
                    "updated_at": func.now(),
                },
            )
            await session.execute(upsert_stmt)
            total += len(batch)
    return total


async def _upsert_stock_status(db: AsyncDatabaseManager, records: list[dict]) -> int:
    """异步批量 UPSERT stock_status 记录."""
    if not records:
        return 0

    seen = {}
    for r in records:
        key = (r["symbol"], r["trade_date"])
        seen[key] = r
    deduped = list(seen.values())

    batch_size = 5000
    total = 0
    async with db.session() as session:
        for i in range(0, len(deduped), batch_size):
            batch = deduped[i : i + batch_size]
            stmt = pg_insert(StockStatus).values(batch)
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "trade_date"],
                set_={
                    "preclose": stmt.excluded.preclose,
                    "high_limited": stmt.excluded.high_limited,
                    "low_limited": stmt.excluded.low_limited,
                    "is_st": stmt.excluded.is_st,
                    "is_susp": stmt.excluded.is_susp,
                    "is_xr": stmt.excluded.is_xr,
                    "is_wd": stmt.excluded.is_wd,
                    "updated_at": func.now(),
                },
            )
            await session.execute(upsert_stmt)
            total += len(batch)
    return total


async def _upsert_backward_factor(
    db: AsyncDatabaseManager, records: list[dict]
) -> int:
    """异步批量 UPSERT backward_factor 记录."""
    if not records:
        return 0

    seen = {}
    for r in records:
        key = (r["symbol"], r["trade_date"])
        seen[key] = r
    deduped = list(seen.values())

    batch_size = 5000
    total = 0
    async with db.session() as session:
        for i in range(0, len(deduped), batch_size):
            batch = deduped[i : i + batch_size]
            stmt = pg_insert(BackwardFactor).values(batch)
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "trade_date"],
                set_={
                    "factor": stmt.excluded.factor,
                    "updated_at": func.now(),
                },
            )
            await session.execute(upsert_stmt)
            total += len(batch)
    return total


# =============================================================================
# 主入口
# =============================================================================
async def main() -> None:
    """主入口（异步）."""
    logger.info("P0 基础数据同步开始")
    logger.info(f"时间: {datetime.now()}")
    logger.info(f"缓存目录: {CACHE_DIR}")
    logger.info(f"批次大小: {BATCH_SIZE}")

    db = await init_db()
    logger.info("数据库表已创建/确认")

    client = await init_api()
    logger.info("API 登录成功")

    try:
        await sync_stock_basic(client, db)

        stock_df = await asyncio.to_thread(client.get_stock_list, "EXTRA_STOCK_A")
        codes = stock_df.index.tolist()
        logger.info(f"获取到 {len(codes)} 只 A 股代码")

        await sync_stock_status(client, db, codes)
        await sync_backward_factor(client, db, codes)

    finally:
        await api_logout(client)
        await db.close()
        logger.info("API 已登出，数据库连接已关闭")

    logger.info("=" * 50)
    logger.info("P0 基础数据同步完成")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
