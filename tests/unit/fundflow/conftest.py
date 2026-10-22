"""资金流向 CLI 命令测试共享 fixture."""

import argparse
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_fundflow_job():
    """mock FundFlowSyncJob。run_daily/run_daily_force 记录调用，默认无返回值."""
    job = MagicMock()
    job.run_daily = AsyncMock(return_value=None)
    job.run_daily_force = AsyncMock(return_value=None)
    return job


def make_args(**overrides) -> argparse.Namespace:
    """构造 CLI 参数 Namespace（默认合法组合：target=all, force=False, date=None）."""
    defaults = {
        "target": "all",
        "date": None,
        "force": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)
