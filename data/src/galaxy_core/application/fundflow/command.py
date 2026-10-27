"""资金流向数据命令处理模块."""

import argparse
import logging
from datetime import date
from typing import Protocol

logger = logging.getLogger(__name__)


class _FundFlowJob(Protocol):
    """资金流向同步 job 协议（FundFlowSyncJob 接口）.

    对齐 02-PLAN-07 ``FundFlowSyncJob.run_daily`` / ``run_daily_force`` 签名
    （``target`` 关键字参数，默认 ``all``）。
    """

    async def run_daily(self, today: date, target: str = "all") -> None: ...
    async def run_daily_force(self, today: date, target: str = "all") -> None: ...


def _parse_date(value: str | None) -> date:
    """解析 YYYYMMDD → date。None 或非法抛 ValueError（由调用者转返回码 1）。"""
    if value is None:
        return date.today()
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except (ValueError, IndexError) as e:
        raise ValueError(f"无效日期格式（应为 YYYYMMDD）: {value!r}") from e


async def handle_fundflow_command_async(
    args: argparse.Namespace,
    fundflow_job: _FundFlowJob | None = None,
) -> int:
    """处理 fundflow 命令.

    按 ``--target`` 选同步目标，``--force`` 选 force 变体。单 job，target 路由
    在 job 内部完成（02-PLAN-07 ``run_daily(today, target=...)`` 分派）。

    Args:
        args: CLI 参数（target / date / force）
        fundflow_job: FundFlowSyncJob 实例（DI 注入）

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

        # 2. job 必须注入
        if fundflow_job is None:
            logger.error("fundflow_job 未注入")
            return 1

        # 3. 按 force 选方法，target 透传给 job 内部分派
        target = getattr(args, "target", "all")
        force = getattr(args, "force", False)
        method = "run_daily_force" if force else "run_daily"

        logger.info(
            f"同步资金流向数据: target={target}, "
            f"date={target_date.strftime('%Y%m%d')}, force={force}"
        )

        # 4. 调度（--force 走公共 run_daily_force，不裸调私有 _sync_<X>）
        logger.info(f"调 {method}(target={target!r})")
        await getattr(fundflow_job, method)(target_date, target=target)

        logger.info("资金流向数据同步命令执行完成")
        return 0

    except KeyboardInterrupt:
        logger.warning("操作被取消")
        return 130
    except Exception:
        logger.exception("命令执行失败")
        return 1
