"""指数 CLI 命令测试共享 fixture."""

import argparse
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_exchange_job():
    """mock ExchangeIndexSyncJob。四个入口都记录调用，默认无返回值."""
    job = MagicMock()
    job.run_daily = AsyncMock(return_value=None)
    job.run_daily_force = AsyncMock(return_value=None)
    job.run_dimensions = AsyncMock(return_value=None)
    job.run_dimensions_force = AsyncMock(return_value=None)
    return job


@pytest.fixture
def mock_industry_job():
    """mock IndustryIndexSyncJob。结构与 exchange job 相同."""
    job = MagicMock()
    job.run_daily = AsyncMock(return_value=None)
    job.run_daily_force = AsyncMock(return_value=None)
    job.run_dimensions = AsyncMock(return_value=None)
    job.run_dimensions_force = AsyncMock(return_value=None)
    return job


def make_args(**overrides) -> argparse.Namespace:
    """构造 CLI 参数 Namespace（默认合法组合）."""
    defaults = {
        "target": "daily",
        "source": "exchange",
        "date": None,
        "force": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)
