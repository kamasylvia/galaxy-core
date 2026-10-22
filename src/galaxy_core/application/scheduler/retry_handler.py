"""带固定间隔的重试处理器.

重试由固定间隔和最大次数决定：
- 初始尝试 1 次
- 失败后最多重试 max_retries 次
- 每次重试前等待固定时长 retry_delay 秒
"""

import asyncio
import logging
from dataclasses import dataclass

from galaxy_core.shared_kernel.utils.config_loader import get_section

logger = logging.getLogger(__name__)


@dataclass
class RetryPolicy:
    """重试配置：固定间隔 + 最大次数."""

    max_retries: int = 3
    retry_delay: int = 300  # 5 minutes in seconds

    @classmethod
    def from_config(cls, sync_type: str | None = None) -> "RetryPolicy":
        """从配置加载重试策略.

        Args:
            sync_type: 同步类型字符串(如 "kline_day")。前缀匹配
                [scheduler.<prefix>] 子表覆盖全局默认。当前仅 "kline_" 前缀
                有子表(凌晨 AM 返空需更长重试窗口),其他走全局。
        """
        config = get_section("scheduler")
        max_retries = config.get("max_retries", 3)
        delay_minutes = config.get("retry_delay_minutes", 5)

        # per-sync_type 子表覆盖(前缀匹配,如 "kline_day" → [scheduler.kline])
        if sync_type:
            for prefix, overrides in config.items():
                if (
                    isinstance(overrides, dict)
                    and sync_type.startswith(prefix + "_")
                ):
                    max_retries = overrides.get("max_retries", max_retries)
                    delay_minutes = overrides.get(
                        "retry_delay_minutes", delay_minutes
                    )
                    break  # 第一个匹配的子表生效

        retry_delay = delay_minutes * 60
        return cls(max_retries=max_retries, retry_delay=retry_delay)


async def sync_with_retry(
    sync_func: callable,
    sync_name: str,
    *args,
    sync_type: str | None = None,
    **kwargs
) -> bool:
    """执行带重试的同步.

    Args:
        sync_func: 要执行的异步函数
        sync_name: 用于日志的人类可读名称
        sync_type: 同步类型(如 "kline_day"),用于选 [scheduler.<prefix>]
            子表覆盖全局重试策略。None 走全局默认。
        *args: 传递给 sync_func 的参数
        **kwargs: 传递给 sync_func 的关键字参数

    Returns:
        同步成功返回 True，所有重试耗尽返回 False
    """
    policy = RetryPolicy.from_config(sync_type)

    # 初始尝试
    try:
        await sync_func(*args, **kwargs)
        logger.info(f"{sync_name} 同步成功")
        return True
    except Exception as e:
        _log_sync_failure(sync_name, e, "初始尝试")

    # 重试
    for retry in range(policy.max_retries):
        try:
            await sync_func(*args, **kwargs)
            logger.info(f"{sync_name} 同步成功（第 {retry + 1} 次重试）")
            return True
        except Exception as e:
            _log_sync_failure(sync_name, e, f"第 {retry + 1} 次重试")
            # 仅在还有下一次重试时 sleep(2026-08-20 修复):原实现最后一次重试
            # 失败后仍 sleep 一个 retry_delay 才标 failed——纯浪费,把 scheduler
            # 后续 job 拖晚 1 小时(实测 8/14/8/20 kline 失败日 fundflow 被拖到
            # 06:14+ 才跑,而 AM 已在 06:14 恢复)。
            if retry < policy.max_retries - 1:
                logger.info(f"将在 {policy.retry_delay // 60} 分钟后重试...")
                await asyncio.sleep(policy.retry_delay)

    logger.error(f"{sync_name} 同步失败，已重试 {policy.max_retries} 次")
    return False


def _log_sync_failure(sync_name: str, e: BaseException, stage: str) -> None:
    """统一记录同步失败(2026-07-29 观测盲区修复)。

    原仅 `logger.error(f"...: {e}")`,但 asyncio.TimeoutError / TimeoutError 的
    str(e) 是空字符串(8/1 industry_daily/weight 失败日志「同步失败: 」后面空白),
    无法定位根因。改为:str(e) 为空时用 type(e).__name__,并加 exc_info=True
    保留 traceback。
    """
    msg = str(e).strip()
    if not msg:
        # TimeoutError 等异常 str 为空,用类型名补全
        msg = f"{type(e).__name__} (无 message)"
    logger.error(f"{sync_name} 同步失败（{stage}）: {msg}", exc_info=True)
