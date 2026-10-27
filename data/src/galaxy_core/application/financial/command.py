"""财务数据命令处理模块."""

import argparse
import logging
from typing import Any

from galaxy_core.domain.value_objects import FinancialDataType
from galaxy_core.services.financial_data_service import FinancialDataService

logger = logging.getLogger(__name__)

# CLI 字符串 → FinancialDataType 枚举映射
_DATA_TYPE_MAP: dict[str, FinancialDataType] = {
    "balance_sheet": FinancialDataType.BALANCE_SHEET,
    "cash_flow": FinancialDataType.CASH_FLOW,
    "income": FinancialDataType.INCOME,
    "profit_express": FinancialDataType.PROFIT_EXPRESS,
    "profit_notice": FinancialDataType.PROFIT_NOTICE,
    "dividend": FinancialDataType.DIVIDEND,
}


async def handle_financial_command_async(
    args: argparse.Namespace,
    financial_service: Any = None,
) -> int:
    """处理 financial 命令.

    解析 args.type 为 FinancialDataType，调用 FinancialDataService.sync()，
    打印同步结果统计。

    Args:
        args: CLI 参数
        financial_service: FinancialDataService 实例（DI 注入）

    Returns:
        0 成功，1 失败
    """
    try:
        # 1. 解析 data_type
        data_type = _DATA_TYPE_MAP.get(args.type)
        if data_type is None:
            logger.error(f"不支持的财务数据类型: {args.type}")
            return 1

        # 2. 构建 symbols 参数
        symbols: list[str] | None = None
        if args.symbol:
            symbols = [args.symbol]

        # 3. 校验服务注入
        if financial_service is None:
            logger.error("financial_service 未注入")
            return 1

        logger.info(
            f"同步财务数据: type={args.type}, "
            f"symbol={args.symbol or '全部 A 股'}, "
            f"start={args.start or '自动'}, end={args.end or '自动'}, "
            f"full_refresh={args.full_refresh}"
        )

        # 4. 调用服务同步
        result = await financial_service.sync(
            data_type=data_type,
            symbols=symbols,
            start=args.start,
            end=args.end,
            full_refresh=args.full_refresh,
        )

        # 5. 打印结果
        logger.info(
            f"同步完成: {result.success_count}/{result.total_symbols} 只证券成功, "
            f"{result.synced_records} 条记录"
        )
        if result.failed_codes:
            logger.warning(f"失败 {len(result.failed_codes)} 只: {result.failed_codes[:10]}")

        return 0

    except KeyboardInterrupt:
        logger.warning("操作被取消")
        return 130
    except Exception:
        logger.exception("命令执行失败")
        return 1
