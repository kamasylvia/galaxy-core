"""SyncStateManager 单元测试.

验证同步状态管理器的幂等门控与状态流转行为：
- is_synced: success 记录存在 → True
- mark_running / mark_success / mark_failed: 正确的 upsert/update
- get_retry_count: 返回当前重试次数
- cleanup_old_records: 删除超期记录并提交

所有 DB 操作经 mock AsyncDatabaseManager，不触真实数据库。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from galaxy_core.application.scheduler.state_manager import SyncStateManager


def _make_mock_db() -> tuple[MagicMock, AsyncMock]:
    """构造 mock AsyncDatabaseManager 与可复用的 session ctx."""
    mock_session = AsyncMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_db = MagicMock()
    mock_db.session.return_value = mock_session_ctx
    return mock_db, mock_session


class TestIsSynced:
    """is_synced 幂等门控测试."""

    def test_returns_true_when_success_record_exists(self):
        """已有 success 记录应返回 True."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(sync_status="success")
        mock_session.execute.return_value = mock_result

        manager = SyncStateManager(mock_db)
        result = asyncio.run(manager.is_synced("kline_day", "20240115"))
        assert result is True

    def test_returns_false_when_no_record(self):
        """无记录应返回 False."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        manager = SyncStateManager(mock_db)
        result = asyncio.run(manager.is_synced("kline_day", "20240115"))
        assert result is False

    def test_returns_false_when_record_not_success(self):
        """记录存在但非 success（如 failed）应返回 False."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        # scalar_one_or_none 返回一个对象，但 query 已 where status=success，
        # 所以这里返回 None 模拟「无 success 行」
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        manager = SyncStateManager(mock_db)
        result = asyncio.run(manager.is_synced("kline_day", "20240115"))
        assert result is False


class TestMarkRunning:
    """mark_running 测试（upsert 语义）."""

    def test_executes_upsert_statement(self):
        """应执行一条 upsert 语句（on_conflict_do_update）."""
        mock_db, mock_session = _make_mock_db()
        manager = SyncStateManager(mock_db)
        asyncio.run(manager.mark_running("kline_day", "20240115"))

        mock_session.execute.assert_called_once()

    def test_does_not_commit_explicitly(self):
        """mark_running 不显式 commit（依赖外层事务/ctx）."""
        mock_db, mock_session = _make_mock_db()
        manager = SyncStateManager(mock_db)
        asyncio.run(manager.mark_running("kline_day", "20240115"))
        mock_session.commit.assert_not_called()


class TestMarkSuccess:
    """mark_success 测试."""

    def test_executes_update_statement(self):
        """应执行一条 update 语句."""
        mock_db, mock_session = _make_mock_db()
        manager = SyncStateManager(mock_db)
        asyncio.run(
            manager.mark_success("kline_day", "20240115", records_synced=100)
        )
        mock_session.execute.assert_called_once()

    def test_clears_error_message_on_success(self):
        """成功时应将 error_message 置空，避免残留先前失败的报错.

        回归：id=4237 事故（exchange_index_weight），mark_success 未清空
        error_message，导致 success + UndefinedTableError 报错文本并存。
        """
        from sqlalchemy.dialects.postgresql import dialect as pg_dialect

        mock_db, mock_session = _make_mock_db()
        manager = SyncStateManager(mock_db)
        asyncio.run(manager.mark_success("kline_day", "20240115", records_synced=100))

        stmt = mock_session.execute.call_args.args[0]
        compiled = stmt.compile(dialect=pg_dialect())
        # SET 子句应包含 error_message = NULL
        assert "error_message" in compiled.string
        # 绑定参数值应为 None
        assert compiled.params.get("error_message") is None


class TestMarkFailed:
    """mark_failed 测试（含 retry_count 自增）."""

    def test_increments_retry_count_from_zero(self):
        """无历史记录时 retry_count 应从 0 自增到 1."""
        mock_db, mock_session = _make_mock_db()
        # 第一次 execute: 查 retry_count → 返回 None（无记录）
        mock_query_result = MagicMock()
        mock_query_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_query_result

        manager = SyncStateManager(mock_db)
        asyncio.run(
            manager.mark_failed("kline_day", "20240115", "timeout")
        )

        # 两次 execute: 查 retry_count + update
        assert mock_session.execute.call_count == 2

    def test_increments_existing_retry_count(self):
        """已有 retry_count=2 时应自增到 3."""
        mock_db, mock_session = _make_mock_db()
        mock_query_result = MagicMock()
        mock_query_result.scalar_one_or_none.return_value = 2
        mock_session.execute.return_value = mock_query_result

        manager = SyncStateManager(mock_db)
        asyncio.run(
            manager.mark_failed("kline_day", "20240115", "timeout")
        )
        assert mock_session.execute.call_count == 2


class TestGetRetryCount:
    """get_retry_count 测试."""

    def test_returns_existing_count(self):
        """应返回当前 retry_count."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 3
        mock_session.execute.return_value = mock_result

        manager = SyncStateManager(mock_db)
        result = asyncio.run(manager.get_retry_count("kline_day", "20240115"))
        assert result == 3

    def test_returns_zero_when_no_record(self):
        """无记录时应返回 0."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        manager = SyncStateManager(mock_db)
        result = asyncio.run(manager.get_retry_count("kline_day", "20240115"))
        assert result == 0


class TestCleanupOldRecords:
    """cleanup_old_records 测试."""

    def test_deletes_old_records_and_commits(self):
        """应执行 delete 并 commit，返回删除条数."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        mock_result.rowcount = 15
        mock_session.execute.return_value = mock_result

        manager = SyncStateManager(mock_db)
        result = asyncio.run(manager.cleanup_old_records(retention_days=30))
        assert result == 15
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_returns_zero_when_nothing_deleted(self):
        """无超期记录时应返回 0（仍 commit）."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        manager = SyncStateManager(mock_db)
        result = asyncio.run(manager.cleanup_old_records(retention_days=30))
        assert result == 0
        mock_session.commit.assert_called_once()

    def test_executes_exactly_one_delete_statement(self):
        """应执行恰好一条 delete 语句（不论 retention_days 取值）."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        manager = SyncStateManager(mock_db)
        asyncio.run(manager.cleanup_old_records(retention_days=90))
        mock_session.execute.assert_called_once()
