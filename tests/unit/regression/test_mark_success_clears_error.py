"""回归测试 — SyncStateManager.mark_success 清 error_message(AGENTS.md 2026-06-17 bug 2/3).

2026-06-17 审计发现 mark_success 的 UPDATE 未置空 error_message,导致 success 行
残留先前失败的报错文本(生产 808 条受影响)。修复:UPDATE 显式 error_message=None。

本回归双轨验证:
1. 源码 grep:state_manager.mark_success 的 UPDATE .values() 含 error_message=None
2. 运行时:mock AsyncDatabaseManager(db.session() 异步上下文管理器),mark_failed
   → mark_success → 捕获 UPDATE stmt,断言 error_message=NULL

mock 模式镜像 tests/unit/scheduler/test_state_manager.py:_make_mock_db()。
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from galaxy_core.application.scheduler.state_manager import SyncStateManager

STATE_MANAGER_PATH = (
    "src/galaxy_core/application/scheduler/state_manager.py"
)


def _make_mock_db() -> tuple[MagicMock, AsyncMock]:
    """构造 mock AsyncDatabaseManager + 可复用 session ctx.

    镜像 tests/unit/scheduler/test_state_manager.py:_make_mock_db()。
    """
    mock_session = AsyncMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_db = MagicMock()
    mock_db.session.return_value = mock_session_ctx
    return mock_db, mock_session


class TestSourceCodeClearsError:
    """源码层:mark_success 的 UPDATE 必须显式置 error_message=None."""

    def test_mark_success_values_contains_error_message_none(self):
        src = Path(STATE_MANAGER_PATH).read_text()
        assert "error_message=None" in src, (
            "state_manager.mark_success 的 .values() 必须含 error_message=None — "
            "AGENTS.md 2026-06-17 bug 2/3 修复点"
        )


class TestMarkSuccessUpdateClearsError:
    """运行时:mark_success UPDATE 置 error_message=None(compile literal binds)."""

    @pytest.mark.asyncio
    async def test_mark_success_update_sets_error_message_none(self):
        """mark_success UPDATE compile 后含 error_message=NULL."""
        mock_db, mock_session = _make_mock_db()
        sm = SyncStateManager(mock_db)

        await sm.mark_success("test_type", "20240115", records_synced=5)

        # 找 UPDATE stmt
        executed = mock_session.execute.call_args_list
        assert executed, "mark_success 应 execute 至少 1 stmt"
        stmt = executed[0].args[0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "error_message=NULL" in compiled, (
            f"mark_success UPDATE 必须置 error_message=NULL,实际:{compiled}"
        )

    @pytest.mark.asyncio
    async def test_mark_failed_keeps_error_message(self):
        """mark_failed UPDATE 含传入的错误文本(不清)."""
        mock_db, mock_session = _make_mock_db()
        # mark_failed 先 query retry_count(scalar_one_or_none),再 update
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = 0
        mock_session.execute.side_effect = [query_result, MagicMock()]
        sm = SyncStateManager(mock_db)

        await sm.mark_failed("test_type", "20240115", "boom")

        # 第二次 execute 调用是 UPDATE stmt
        update_call = mock_session.execute.call_args_list[1]
        stmt = update_call.args[0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "boom" in compiled, "mark_failed UPDATE 应含错误文本"
        assert "error_message=NULL" not in compiled, (
            "mark_failed 不应置 error_message=NULL(它写入错误)"
        )
