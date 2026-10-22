"""交易所指数同步任务单元测试.

验证 run_daily / run_dimensions 的状态管理流程（去重、首次强制、失败标记）。
所有 provider/store 调用 mock。
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

# NOTE: 这些测试在导入时会拉取 pandas（job 模块依赖）。
# 若运行环境缺少 libstdc++（pandas 无法加载），测试会跳过而非失败。
pd = pytest.importorskip("pandas")

from galaxy_core.application.scheduler.jobs.exchange_index_sync_job import (  # noqa: E402
    ExchangeIndexSyncJob,
)


@pytest.fixture
def mock_provider():
    p = MagicMock()
    p.get_index_constituent = AsyncMock(return_value={})
    p.get_index_weight = AsyncMock(return_value={})
    p.get_index_code_list = AsyncMock(return_value=["000300.SH"])
    return p


@pytest.fixture
def mock_store():
    s = MagicMock()
    s.save_index_constituent = AsyncMock(return_value=0)
    s.save_index_weight = AsyncMock(return_value=0)
    s.is_index_constituent_empty = AsyncMock(return_value=False)
    return s


@pytest.fixture
def job(mock_state_manager, mock_provider, mock_store, monkeypatch):
    # job 读取 [index] / [amazing_data] 配置段
    fake_config = {
        "index": {"index_weight_codes": ["000300.SH"], "index_security_type": "EXTRA_INDEX_A"},
        "amazing_data": {"local_path": "./data/local_cache/"},
    }
    monkeypatch.setattr(
        "galaxy_core.application.scheduler.jobs.exchange_index_sync_job.get_section",
        lambda key: fake_config.get(key, {}),
    )
    # Phase 03:last_sync_store 需 AsyncMock(get/set 都是 async)
    last_sync_store = MagicMock()
    last_sync_store.get_last_sync_date = AsyncMock(return_value=None)
    last_sync_store.set_last_sync_date = AsyncMock()
    return ExchangeIndexSyncJob(
        state_manager=mock_state_manager,
        provider=mock_provider,
        store=mock_store,
        last_sync_store=last_sync_store,
    )


class TestRunDaily:
    async def test_skips_when_already_synced(self, job, mock_state_manager):
        mock_state_manager.is_synced = AsyncMock(return_value=True)
        today = date(2024, 1, 15)
        await job.run_daily(today)
        mock_state_manager.mark_running.assert_not_called()

    async def test_skips_when_disabled_via_config(self, job, mock_state_manager, mock_provider):
        """disable_index_weight=true → run_daily 早退，不调 provider/state_manager.

        背景：AmazingData API 停供 + SDK 空 DataFrame bug，开关暂停自动同步。
        """
        job._config["disable_index_weight"] = True
        mock_state_manager.is_synced = AsyncMock(return_value=False)  # 即使未同步也短路
        today = date(2024, 1, 15)
        await job.run_daily(today)
        mock_state_manager.mark_running.assert_not_called()
        mock_state_manager.mark_success.assert_not_called()
        mock_provider.get_index_weight.assert_not_called()

    async def test_enabled_by_default_runs_sync(
        self, job, mock_provider, mock_store, mock_state_manager
    ):
        """disable_index_weight 未设（默认 False）→ 正常走同步流程."""
        assert "disable_index_weight" not in job._config  # 显式默认
        mock_provider.get_index_weight = AsyncMock(return_value={})
        mock_store.save_index_weight = AsyncMock(return_value=0)
        today = date(2024, 1, 15)
        await job.run_daily(today)
        mock_provider.get_index_weight.assert_called_once()
        mock_state_manager.mark_success.assert_called_once()

    async def test_marks_success_on_empty_weight(
        self, job, mock_provider, mock_store, mock_state_manager
    ):
        mock_provider.get_index_weight = AsyncMock(return_value={})
        mock_store.save_index_weight = AsyncMock(return_value=0)
        today = date(2024, 1, 15)
        await job.run_daily(today)
        mock_state_manager.mark_success.assert_called_once_with(
            "exchange_index_weight", "20240115", records_synced=0
        )

    async def test_marks_failed_on_exception(self, job, mock_provider, mock_state_manager):
        mock_provider.get_index_weight = AsyncMock(side_effect=RuntimeError("boom"))
        today = date(2024, 1, 15)
        await job.run_daily(today)
        mock_state_manager.mark_failed.assert_called_once()
        args = mock_state_manager.mark_failed.call_args
        assert args[0][0] == "exchange_index_weight"
        assert "boom" in args[0][2]


class TestRunDailyForce:
    """Phase 01：run_daily_force 绕过 is_synced，但仍走状态标记.

    注：run_daily_force 不受 disable_index_weight 开关影响——开关仅暂停 scheduler
    自动同步，手动 --force 补数仍可触发（用于 SDK 修复后手动补缺口）。
    """

    async def test_force_ignores_disable_switch(
        self, job, mock_provider, mock_store, mock_state_manager
    ):
        """disable_index_weight=true 时 run_daily_force 仍执行（不受开关影响）."""
        import pandas as pd
        job._config["disable_index_weight"] = True  # 开关开启
        mock_state_manager.is_synced = AsyncMock(return_value=True)
        mock_provider.get_index_weight = AsyncMock(
            return_value={"000300.SH": pd.DataFrame({
                "INDEX_CODE": ["000300.SH"], "CON_CODE": ["600000.SH"],
                "TRADE_DATE": ["20240115"], "WEIGHT": [0.1],
            })}
        )
        mock_store.save_index_weight = AsyncMock(return_value=3)
        today = date(2024, 1, 15)
        await job.run_daily_force(today)
        mock_state_manager.mark_running.assert_called_once_with(
            "exchange_index_weight", "20240115"
        )
        mock_state_manager.mark_success.assert_called_once_with(
            "exchange_index_weight", "20240115", records_synced=3
        )

    async def test_reruns_even_if_already_synced(
        self, job, mock_provider, mock_store, mock_state_manager
    ):
        """is_synced=True 也重跑，并更新状态."""
        import pandas as pd
        mock_state_manager.is_synced = AsyncMock(return_value=True)
        mock_provider.get_index_weight = AsyncMock(
            return_value={"000300.SH": pd.DataFrame({
                "INDEX_CODE": ["000300.SH"], "CON_CODE": ["600000.SH"],
                "TRADE_DATE": ["20240115"], "WEIGHT": [0.1],
            })}
        )
        mock_store.save_index_weight = AsyncMock(return_value=7)
        today = date(2024, 1, 15)
        await job.run_daily_force(today)
        # 关键：mark_running 被调（说明没因 is_synced 短路）
        mock_state_manager.mark_running.assert_called_once_with(
            "exchange_index_weight", "20240115"
        )
        mock_state_manager.mark_success.assert_called_once_with(
            "exchange_index_weight", "20240115", records_synced=7
        )

    async def test_marks_failed_on_exception(self, job, mock_provider, mock_state_manager):
        mock_provider.get_index_weight = AsyncMock(side_effect=RuntimeError("boom"))
        today = date(2024, 1, 15)
        await job.run_daily_force(today)
        mock_state_manager.mark_failed.assert_called_once()
        assert mock_state_manager.mark_failed.call_args[0][0] == "exchange_index_weight"


class TestRunDimensions:
    async def test_force_sync_when_empty(self, job, mock_provider, mock_store, mock_state_manager):
        # provider 返回成分股数据 → store 返回 42 条
        import pandas as pd
        mock_provider.get_index_constituent = AsyncMock(
            return_value={"000300.SH": pd.DataFrame(
                {"INDEX_CODE": ["000300.SH"], "CON_CODE": ["600000.SH"], "INDATE": ["20240101"]}
            )}
        )
        mock_store.is_index_constituent_empty = AsyncMock(return_value=True)
        mock_store.save_index_constituent = AsyncMock(return_value=42)
        today = date(2024, 1, 15)  # ISO week W03
        await job.run_dimensions(today)
        # 即使 is_synced=True 也会因空表强制执行
        mock_state_manager.mark_running.assert_called_once()
        mock_state_manager.mark_success.assert_called_once_with(
            "exchange_index_constituent", "2024-W03", records_synced=42
        )

    async def test_skips_when_synced_and_not_empty(self, job, mock_store, mock_state_manager):
        mock_store.is_index_constituent_empty = AsyncMock(return_value=False)
        mock_state_manager.is_synced = AsyncMock(return_value=True)
        today = date(2024, 1, 15)
        await job.run_dimensions(today)
        mock_state_manager.mark_running.assert_not_called()

    async def test_period_id_is_iso_week(self, job, mock_store, mock_state_manager):
        mock_store.is_index_constituent_empty = AsyncMock(return_value=False)
        mock_state_manager.is_synced = AsyncMock(return_value=False)
        # 2024-01-01 是周一，ISO week W01
        await job.run_dimensions(date(2024, 1, 1))
        assert mock_state_manager.mark_running.call_args[0][1] == "2024-W01"


class TestRunDimensionsForce:
    """Phase 01：run_dimensions_force 绕过 is_synced，保留表空强制分支."""

    async def test_reruns_even_if_synced_and_not_empty(
        self, job, mock_provider, mock_store, mock_state_manager
    ):
        """表非空且 is_synced=True → force 仍重跑."""
        import pandas as pd
        mock_provider.get_index_constituent = AsyncMock(
            return_value={"000300.SH": pd.DataFrame({
                "INDEX_CODE": ["000300.SH"], "CON_CODE": ["600000.SH"], "INDATE": ["20240101"]
            })}
        )
        mock_store.is_index_constituent_empty = AsyncMock(return_value=False)
        mock_state_manager.is_synced = AsyncMock(return_value=True)  # force 应绕过
        mock_store.save_index_constituent = AsyncMock(return_value=11)
        today = date(2024, 1, 15)  # W03
        await job.run_dimensions_force(today)
        mock_state_manager.mark_running.assert_called_once_with(
            "exchange_index_constituent", "2024-W03"
        )
        mock_state_manager.mark_success.assert_called_once_with(
            "exchange_index_constituent", "2024-W03", records_synced=11
        )

    async def test_force_still_runs_when_empty(
        self, job, mock_provider, mock_store, mock_state_manager
    ):
        """表空 → force 路径同样执行（不跳过空表初始化）."""
        import pandas as pd
        mock_provider.get_index_constituent = AsyncMock(
            return_value={"000300.SH": pd.DataFrame(
                {"INDEX_CODE": ["000300.SH"], "CON_CODE": ["600000.SH"], "INDATE": ["20240101"]}
            )}
        )
        mock_store.is_index_constituent_empty = AsyncMock(return_value=True)
        mock_store.save_index_constituent = AsyncMock(return_value=1)
        today = date(2024, 1, 15)
        await job.run_dimensions_force(today)
        mock_state_manager.mark_success.assert_called_once_with(
            "exchange_index_constituent", "2024-W03", records_synced=1
        )
