"""指数 CLI 命令处理单元测试."""

from datetime import date

import pytest

from galaxy_core.application.index.command import handle_index_command_async
from tests.unit.index.conftest import make_args


class TestHandleIndexCommand:
    """handle_index_command_async 测试."""

    @pytest.mark.asyncio
    async def test_default_skip_calls_run_daily_not_force(
        self, mock_exchange_job, mock_industry_job
    ):
        """默认 skip 路径：调 run_daily，不调 run_daily_force."""
        args = make_args(target="daily", source="exchange", force=False)

        rc = await handle_index_command_async(
            args,
            exchange_index_job=mock_exchange_job,
            industry_index_job=mock_industry_job,
        )

        assert rc == 0
        mock_exchange_job.run_daily.assert_awaited_once()
        mock_exchange_job.run_daily_force.assert_not_awaited()
        mock_industry_job.run_daily.assert_not_awaited()
        mock_industry_job.run_daily_force.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_force_calls_run_daily_force(self, mock_exchange_job, mock_industry_job):
        """--force 路径：调 run_daily_force，不调 run_daily."""
        args = make_args(target="daily", source="exchange", force=True)

        rc = await handle_index_command_async(
            args,
            exchange_index_job=mock_exchange_job,
            industry_index_job=mock_industry_job,
        )

        assert rc == 0
        mock_exchange_job.run_daily_force.assert_awaited_once()
        mock_exchange_job.run_daily.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dimensions_industry_only(self, mock_exchange_job, mock_industry_job):
        """--target dimensions --source industry：仅 industry job 的 run_dimensions."""
        args = make_args(target="dimensions", source="industry", force=False)

        rc = await handle_index_command_async(
            args,
            exchange_index_job=mock_exchange_job,
            industry_index_job=mock_industry_job,
        )

        assert rc == 0
        mock_industry_job.run_dimensions.assert_awaited_once()
        mock_industry_job.run_dimensions_force.assert_not_awaited()
        mock_exchange_job.run_dimensions.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_both_all_calls_everything(self, mock_exchange_job, mock_industry_job):
        """--source both --target all：两 job 的 daily + dimensions 全调."""
        args = make_args(target="all", source="both", force=False)

        rc = await handle_index_command_async(
            args,
            exchange_index_job=mock_exchange_job,
            industry_index_job=mock_industry_job,
        )

        assert rc == 0
        mock_exchange_job.run_daily.assert_awaited_once()
        mock_exchange_job.run_dimensions.assert_awaited_once()
        mock_industry_job.run_daily.assert_awaited_once()
        mock_industry_job.run_dimensions.assert_awaited_once()
        # force 变体均不应被调
        mock_exchange_job.run_daily_force.assert_not_awaited()
        mock_exchange_job.run_dimensions_force.assert_not_awaited()
        mock_industry_job.run_daily_force.assert_not_awaited()
        mock_industry_job.run_dimensions_force.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_date_passthrough(self, mock_exchange_job, mock_industry_job):
        """--date YYYYMMDD 透传给 job（按 date 对象）。"""
        args = make_args(date="20250613")

        rc = await handle_index_command_async(
            args,
            exchange_index_job=mock_exchange_job,
            industry_index_job=mock_industry_job,
        )

        assert rc == 0
        mock_exchange_job.run_daily.assert_awaited_once_with(date(2025, 6, 13))

    @pytest.mark.asyncio
    async def test_date_invalid_returns_1(self, mock_exchange_job, mock_industry_job):
        """--date 格式非法 → 返回 1，不调任何 job."""
        args = make_args(date="not-a-date")

        rc = await handle_index_command_async(
            args,
            exchange_index_job=mock_exchange_job,
            industry_index_job=mock_industry_job,
        )

        assert rc == 1
        mock_exchange_job.run_daily.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_exchange_job_none_returns_1(self, mock_industry_job):
        """source 含 exchange 但 exchange_index_job=None → 返回 1."""
        args = make_args(source="both")

        rc = await handle_index_command_async(
            args,
            exchange_index_job=None,
            industry_index_job=mock_industry_job,
        )

        assert rc == 1

    @pytest.mark.asyncio
    async def test_industry_job_none_returns_1(self, mock_exchange_job):
        """source 含 industry 但 industry_index_job=None → 返回 1."""
        args = make_args(source="both")

        rc = await handle_index_command_async(
            args,
            exchange_index_job=mock_exchange_job,
            industry_index_job=None,
        )

        assert rc == 1

    @pytest.mark.asyncio
    async def test_industry_only_does_not_require_exchange_job(
        self, mock_industry_job
    ):
        """source=industry 时 exchange_index_job 可为 None 不报错."""
        args = make_args(target="daily", source="industry")

        rc = await handle_index_command_async(
            args,
            exchange_index_job=None,
            industry_index_job=mock_industry_job,
        )

        assert rc == 0
        mock_industry_job.run_daily.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_job_raises_returns_1(self, mock_exchange_job, mock_industry_job):
        """job 抛异常 → 捕获后返回 1（不向 CLI 调用者泄漏异常）。"""
        mock_exchange_job.run_daily.side_effect = RuntimeError("boom")
        args = make_args()

        rc = await handle_index_command_async(
            args,
            exchange_index_job=mock_exchange_job,
            industry_index_job=mock_industry_job,
        )

        assert rc == 1
