"""Universe(证券代码集合)获取 helper.

提供 SDK 优先 + DB fallback 的 universe 解析,规避 SDK `get_hist_code_list`
在凌晨 AM 时段返空(2026-07-28 P0 bug,kline/fundflow/financial 连环空跑)。

背景见 AGENTS.md 2026-07-28 Bug 2:
- SDK `get_hist_code_list(start=T, end=T)` 单日端点凌晨返 0(AM 时段性不稳,
  联网补缺 pkl 失败 → union 空)
- 修法: 区间 [T-30, T] 让 SDK union 多日 pkl;返空时 fallback 从 stock_basic 表读
"""
import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import or_, select

from galaxy_core.database.models.stock_basic import StockBasic
from galaxy_core.domain.symbol.type_inference import to_broad_security_type

logger = logging.getLogger(__name__)


# 回溯天数:让 SDK 在区间内 union 多日 pkl,降低单日联网补缺失败的影响
DEFAULT_HISTORY_DAYS = 30


async def resolve_universe_with_fallback(
    reference_provider: Any,
    db_manager: Any,
    security_type: str,
    end_date: date,
    local_path: str,
    history_days: int = DEFAULT_HISTORY_DAYS,
) -> list[str]:
    """SDK 优先(区间 union),返空时 fallback 从 stock_basic 表读 codes.

    Args:
        reference_provider: ReferenceProviderPort(调 get_hist_code_list)
        db_manager: AsyncDatabaseManager(fallback 查 stock_basic);None 时跳过 fallback(CLI 场景)
        security_type: security_type 名称(如 EXTRA_ETF / EXTRA_STOCK_A / EXTRA_STOCK_A_SH_SZ)
        end_date: 区间结束日(通常 today 或 today-1)
        local_path: SDK 本地缓存路径
        history_days: 区间回溯天数,默认 30

    Returns:
        去重后的 code 列表(可能为空)
    """
    # Step 1: SDK 区间查询(让 union 多日 pkl,降低单日联网失败影响)
    start_date_int = int((end_date - timedelta(days=history_days)).strftime("%Y%m%d"))
    end_date_int = int(end_date.strftime("%Y%m%d"))

    sdk_codes: list[str] = []
    try:
        sdk_codes = await reference_provider.get_hist_code_list(
            security_type=security_type,
            start_date=start_date_int,
            end_date=end_date_int,
            local_path=local_path,
        )
        sdk_codes = list(sdk_codes) if sdk_codes else []
    except Exception as e:
        logger.warning(
            f"SDK get_hist_code_list 异常 ({security_type}, "
            f"{start_date_int}~{end_date_int}): {e}"
        )

    if sdk_codes:
        logger.info(
            f"universe(SDK): {len(sdk_codes)} 只 ({security_type}, "
            f"{start_date_int}~{end_date_int})"
        )
        return sdk_codes

    # Step 2: SDK 返空 → fallback DB stock_basic
    logger.warning(
        f"SDK get_hist_code_list 返空 ({security_type}, "
        f"{start_date_int}~{end_date_int}),fallback 查 stock_basic 表"
    )

    if db_manager is None:
        logger.warning("无 db_manager,跳过 fallback,universe 返空")
        return []

    broad_type = to_broad_security_type(security_type)
    return await _read_active_symbols_from_db(db_manager, broad_type)


async def _read_active_symbols_from_db(
    db_manager: Any, broad_security_type: str
) -> list[str]:
    """从 stock_basic 表读活跃证券 codes(is_listed 为 True 或 NULL).

    Args:
        db_manager: AsyncDatabaseManager
        broad_security_type: 宽泛类型(EXTRA_STOCK_A / EXTRA_ETF / EXTRA_INDEX_A)

    Returns:
        code 列表(可能为空)
    """
    try:
        async with db_manager._engine.connect() as conn:
            stmt = (
                select(StockBasic.symbol)
                .where(
                    StockBasic.security_type == broad_security_type,
                    or_(
                        StockBasic.is_listed.is_(None),
                        StockBasic.is_listed == True,  # noqa: E712
                    ),
                )
            )
            result = await conn.execute(stmt)
            rows = result.all()
            symbols = [row[0] for row in rows]
        logger.info(
            f"universe(DB fallback): {len(symbols)} 只 ({broad_security_type})"
        )
        return symbols
    except Exception as e:
        logger.error(f"stock_basic fallback 查询失败 ({broad_security_type}): {e}")
        return []
