"""指数数据命令处理模块."""

import argparse
import logging
from datetime import date
from typing import Protocol

logger = logging.getLogger(__name__)


class _IndexJob(Protocol):
    """指数同步 job 协议（ExchangeIndexSyncJob / IndustryIndexSyncJob 共同接口）."""

    async def run_daily(self, today: date) -> None: ...
    async def run_daily_force(self, today: date) -> None: ...
    async def run_dimensions(self, today: date) -> None: ...
    async def run_dimensions_force(self, today: date) -> None: ...


def _parse_date(value: str | None) -> date:
    """解析 YYYYMMDD → date。None 或非法返回 today()."""
    if value is None:
        return date.today()
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except (ValueError, IndexError) as e:
        raise ValueError(f"无效日期格式（应为 YYYYMMDD）: {value!r}") from e


async def handle_index_command_async(
    args: argparse.Namespace,
    exchange_index_job: _IndexJob | None = None,
    industry_index_job: _IndexJob | None = None,
) -> int:
    """处理 index 命令.

    按 --source 选 job 集合，按 --target 选方法，--force 选 force 变体。

    Args:
        args: CLI 参数（target / source / date / force）
        exchange_index_job: ExchangeIndexSyncJob 实例（DI 注入）
        industry_index_job: IndustryIndexSyncJob 实例（DI 注入）

    Returns:
        0 成功，1 失败，130 取消
    """
    try:
        # 1. 解析日期
        try:
            target_date = _parse_date(getattr(args, "date", None))
        except ValueError as e:
            logger.error(str(e))
            return 1

        # 2. 按 source 选 job
        source = args.source
        jobs: list[tuple[str, _IndexJob]] = []
        if source in ("exchange", "both"):
            if exchange_index_job is None:
                logger.error("exchange_index_job 未注入")
                return 1
            jobs.append(("exchange", exchange_index_job))
        if source in ("industry", "both"):
            if industry_index_job is None:
                logger.error("industry_index_job 未注入")
                return 1
            jobs.append(("industry", industry_index_job))

        # 3. 按 target + force 选方法
        target = args.target
        force = getattr(args, "force", False)

        daily_method = "run_daily_force" if force else "run_daily"
        dimensions_method = "run_dimensions_force" if force else "run_dimensions"

        logger.info(
            f"同步指数数据: source={source}, target={target}, "
            f"date={target_date.strftime('%Y%m%d')}, force={force}"
        )

        # 4. 调度
        for name, job in jobs:
            if target in ("daily", "all"):
                logger.info(f"[{name}] 调 {daily_method}")
                await getattr(job, daily_method)(target_date)
            if target in ("dimensions", "all"):
                logger.info(f"[{name}] 调 {dimensions_method}")
                await getattr(job, dimensions_method)(target_date)

        logger.info("指数数据同步命令执行完成")
        return 0

    except KeyboardInterrupt:
        logger.warning("操作被取消")
        return 130
    except Exception:
        logger.exception("命令执行失败")
        return 1
