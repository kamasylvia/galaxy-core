"""资金流向 CLI 命令处理单元测试."""

from datetime import date

import pytest

from galaxy_core.application.fundflow.command import handle_fundflow_command_async
from tests.unit.fundflow.conftest import make_args


class TestHandleFundFlowCommand:
    """handle_fundflow_command_async 测试."""

    @pytest.mark.asyncio
    async def test_handle_no_force_calls_run_daily(self, mock_fundflow_job):
        """默认 skip 路径：调 run_daily，不调 run_daily_force。"""
        args = make_args(target="all", force=False)

        rc = await handle_fundflow_command_async(args, fundflow_job=mock_fundflow_job)

        assert rc == 0
        mock_fundflow_job.run_daily.assert_awaited_once()
        mock_fundflow_job.run_daily_force.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handle_force_calls_run_daily_force(self, mock_fundflow_job):
        """--force 路径：调 run_daily_force，不调 run_daily。"""
        args = make_args(target="all", force=True)

        rc = await handle_fundflow_command_async(args, fundflow_job=mock_fundflow_job)

        assert rc == 0
        mock_fundflow_job.run_daily_force.assert_awaited_once()
        mock_fundflow_job.run_daily.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handle_passes_target(self, mock_fundflow_job):
        """--target sector → run_daily(date, target='sector')（target 透传 job 内部分派）。"""
        args = make_args(target="sector", force=False)

        rc = await handle_fundflow_command_async(args, fundflow_job=mock_fundflow_job)

        assert rc == 0
        mock_fundflow_job.run_daily.assert_awaited_once()
        called_args, called_kwargs = mock_fundflow_job.run_daily.call_args
        # today 为位置参数，target 为关键字参数
        assert called_kwargs.get("target") == "sector"

    @pytest.mark.asyncio
    async def test_handle_force_passes_target(self, mock_fundflow_job):
        """--force --target margin → run_daily_force(date, target='margin')。"""
        args = make_args(target="margin", force=True)

        rc = await handle_fundflow_command_async(args, fundflow_job=mock_fundflow_job)

        assert rc == 0
        mock_fundflow_job.run_daily_force.assert_awaited_once()
        _, called_kwargs = mock_fundflow_job.run_daily_force.call_args
        assert called_kwargs.get("target") == "margin"

    @pytest.mark.asyncio
    async def test_handle_returns_0_on_success(self, mock_fundflow_job):
        """成功路径返回 0。"""
        args = make_args()

        rc = await handle_fundflow_command_async(args, fundflow_job=mock_fundflow_job)

        assert rc == 0

    @pytest.mark.asyncio
    async def test_handle_returns_1_on_exception(self, mock_fundflow_job):
        """job 抛异常 → 捕获后返回 1（不向 CLI 调用者泄漏异常）。"""
        mock_fundflow_job.run_daily.side_effect = RuntimeError("boom")
        args = make_args()

        rc = await handle_fundflow_command_async(args, fundflow_job=mock_fundflow_job)

        assert rc == 1

    @pytest.mark.asyncio
    async def test_handle_returns_130_on_keyboard_interrupt(self, mock_fundflow_job):
        """job 抛 KeyboardInterrupt → 返回 130（取消）。"""
        mock_fundflow_job.run_daily.side_effect = KeyboardInterrupt()
        args = make_args()

        rc = await handle_fundflow_command_async(args, fundflow_job=mock_fundflow_job)

        assert rc == 130

    @pytest.mark.asyncio
    async def test_handle_date_invalid_returns_1(self, mock_fundflow_job):
        """--date 格式非法 → 返回 1，不调任何 job。"""
        args = make_args(date="not-a-date")

        rc = await handle_fundflow_command_async(args, fundflow_job=mock_fundflow_job)

        assert rc == 1
        mock_fundflow_job.run_daily.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handle_date_passthrough(self, mock_fundflow_job):
        """--date YYYYMMDD 透传给 job（按 date 对象）。"""
        args = make_args(date="20260616", force=False)

        rc = await handle_fundflow_command_async(args, fundflow_job=mock_fundflow_job)

        assert rc == 0
        called_args, _ = mock_fundflow_job.run_daily.call_args
        assert called_args[0] == date(2026, 6, 16)

    @pytest.mark.asyncio
    async def test_handle_job_none_returns_1(self):
        """fundflow_job 未注入 → 返回 1。"""
        args = make_args()

        rc = await handle_fundflow_command_async(args, fundflow_job=None)

        assert rc == 1

    @pytest.mark.asyncio
    async def test_handle_default_target_all(self, mock_fundflow_job):
        """Namespace 无 target 属性时 getattr 默认 'all'（防御性）。"""
        args = make_args()
        del args.target

        rc = await handle_fundflow_command_async(args, fundflow_job=mock_fundflow_job)

        assert rc == 0
        _, called_kwargs = mock_fundflow_job.run_daily.call_args
        assert called_kwargs.get("target") == "all"
