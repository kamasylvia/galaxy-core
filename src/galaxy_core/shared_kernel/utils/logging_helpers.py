"""日志辅助工具模块.

提供批量操作进度跟踪和结构化日志输出的共享工具函数，消除重复日志模式。
包含:
- BatchProgressLogger: 批量操作进度跟踪器
- log_sync_result: 同步结果汇总输出
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class BatchProgressLogger:
    """批量操作进度跟踪器.

    跟踪批量操作进度，在配置的间隔处输出 DEBUG 级别进度信息，
    操作完成时输出 INFO 级别汇总。

    用法示例::

        progress = BatchProgressLogger(total=3007, operation_name="stock_basic")
        for i, item in enumerate(items):
            # 处理逻辑...
            progress.update()
        progress.complete(success_count=saved_count)
    """

    def __init__(self, total: int, operation_name: str, log_interval: int = 100) -> None:
        """初始化进度跟踪器.

        Args:
            total: 总处理数量
            operation_name: 操作名称，用于日志输出
            log_interval: 日志输出间隔，默认每 100 条输出一次
        """
        self.total = total
        self.operation_name = operation_name
        self.log_interval = log_interval
        self.processed: int = 0

    def update(self, count: int = 1) -> None:
        """更新进度计数器.

        在达到配置间隔时输出 DEBUG 级别进度日志。

        Args:
            count: 本次更新的处理数量，默认为 1
        """
        self.processed += count
        if self.processed % self.log_interval == 0:
            logger.debug(f"{self.operation_name} 进度: {self.processed}/{self.total}")

    def complete(self, success_count: int | None = None) -> None:
        """输出操作完成汇总.

        Args:
            success_count: 成功处理的数量，如果提供则显示成功数/总数
        """
        if success_count is not None:
            logger.info(f"{self.operation_name}: 完成，成功 {success_count}/{self.total}")
        else:
            logger.info(f"{self.operation_name}: 完成，共 {self.processed} 条")


def log_sync_result(sync_result: object) -> None:
    """输出同步结果汇总.

    以分隔符包裹的结构化格式输出同步结果，包括成功代码数、成功记录数、
    失败代码数及失败详情。

    Args:
        sync_result: 同步结果对象，需包含以下属性:
            - success_count: int — 成功同步的代码数
            - synced_records: int — 成功同步的记录数
            - failed_codes: list[str] — 失败的代码列表
    """
    logger.info("=" * 50)
    logger.info("同步完成！")
    logger.info("-" * 50)
    logger.info(f"同步成功代码数: {sync_result.success_count}")
    logger.info(f"同步成功记录数: {sync_result.synced_records:,} 条")
    logger.info(f"同步失败代码数: {len(sync_result.failed_codes)}")

    if sync_result.failed_codes:
        max_display = 10
        failed_str = ", ".join(sync_result.failed_codes[:max_display])
        if len(sync_result.failed_codes) > max_display:
            failed_str += f" ... (共 {len(sync_result.failed_codes)} 只)"
        logger.info(f"失败代码: {failed_str}")
    logger.info("=" * 50)
