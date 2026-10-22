"""财务数据同步调度任务 — 每月全量刷新全部 5 种财务数据类型.

每种 data_type 独立管理 SyncStateManager 状态，单种失败不阻断其余类型。
"""

import logging
from datetime import date
from typing import Any

from galaxy_core.application.scheduler.state_manager import SyncStateManager
from galaxy_core.domain.value_objects import FinancialDataType
from galaxy_core.services.financial_data_service import FinancialDataService

logger = logging.getLogger(__name__)

# 全部 6 种财务数据类型，按同步顺序排列
_ALL_DATA_TYPES: list[FinancialDataType] = [
    FinancialDataType.BALANCE_SHEET,
    FinancialDataType.CASH_FLOW,
    FinancialDataType.INCOME,
    FinancialDataType.PROFIT_EXPRESS,
    FinancialDataType.PROFIT_NOTICE,
    FinancialDataType.DIVIDEND,
]


class FinancialSyncJob:
    """财务数据同步调度任务.

    每月执行一次全量刷新（覆盖最近 3 年），独立管理每种 data_type 的同步状态。
    """

    def __init__(
        self,
        state_manager: SyncStateManager,
        financial_service: FinancialDataService,
        reference_provider: Any = None,
    ) -> None:
        self._state_manager = state_manager
        self._financial_service = financial_service
        self._reference_provider = reference_provider

    async def run(self, today: date) -> None:
        """执行全部 5 种财务数据类型的月度全量刷新.

        每种 data_type 独立管理 sync_state：
        - sync_type = financial_{data_type.value}
        - period_id = YYYY-MM（月度批次标识）
        - 已同步的跳过，失败的不阻断其余类型

        Args:
            today: 当前日期
        """
        period_id = f"{today.year}-{today.month:02d}"
        success_count = 0
        failed_types: list[str] = []

        logger.info(f"开始月度财务数据全量刷新，period_id={period_id}")

        for data_type in _ALL_DATA_TYPES:
            sync_type = f"financial_{data_type.value}"

            # 检查是否已同步
            if await self._state_manager.is_synced(sync_type, period_id):
                logger.info(f"{sync_type} {period_id} 已同步，跳过")
                continue

            # 标记 running
            await self._state_manager.mark_running(sync_type, period_id)

            try:
                result = await self._financial_service.sync(
                    data_type=data_type,
                    full_refresh=True,
                )
                await self._state_manager.mark_success(
                    sync_type, period_id, records_synced=result.synced_records
                )
                success_count += 1
                logger.info(
                    f"{data_type.value} 同步完成: "
                    f"{result.success_count}/{result.total_symbols} 只证券, "
                    f"{result.synced_records} 条记录"
                )
            except Exception as e:
                await self._state_manager.mark_failed(sync_type, period_id, str(e))
                failed_types.append(data_type.value)
                logger.error(f"{data_type.value} 同步失败: {e}")
                # 继续执行剩余 data_type

        # 汇总日志
        if failed_types:
            logger.warning(
                f"月度财务数据刷新完成（部分失败）: "
                f"{success_count} 种成功, {len(failed_types)} 种失败: {failed_types}"
            )
        else:
            logger.info(
                f"月度财务数据刷新完成: {success_count} 种财务数据全部成功"
            )
