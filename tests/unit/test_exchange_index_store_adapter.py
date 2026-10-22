"""ExchangeIndexStoreAdapter 测试.

验证 adapter 满足 ExchangeIndexStorePort Protocol，并能正确 UPSERT
IndexConstituent / IndexWeight 值对象。所有 DB 操作经 mock AsyncDatabaseManager，
不触真实数据库。镜像 test_kline_store_adapter.py 的测试约定。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from galaxy_core.database.services.adapters.exchange_index_store_adapter import (
    ExchangeIndexStoreAdapter,
)
from galaxy_core.domain.ports.exchange_index_store import ExchangeIndexStorePort
from galaxy_core.domain.value_objects import IndexConstituent, IndexWeight
from galaxy_core.shared_kernel.exceptions import CacheError


def _make_mock_db() -> tuple[MagicMock, AsyncMock]:
    """构造 mock AsyncDatabaseManager 与可复用的 session ctx.

    返回 (mock_db, mock_session)。调用方按需在 mock_session 上挂返回值。
    """
    mock_session = AsyncMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_db = MagicMock()
    mock_db.session.return_value = mock_session_ctx
    return mock_db, mock_session


class TestExchangeIndexStoreAdapterProtocol:
    """验证 ExchangeIndexStoreAdapter 满足 ExchangeIndexStorePort Protocol."""

    def test_adapter_is_protocol_instance(self):
        """ExchangeIndexStoreAdapter 应满足 ExchangeIndexStorePort Protocol."""
        mock_db = MagicMock()
        adapter = ExchangeIndexStoreAdapter(mock_db)
        assert isinstance(adapter, ExchangeIndexStorePort)

    def test_adapter_has_async_save_index_constituent(self):
        """save_index_constituent 应为 async 方法."""
        import inspect

        mock_db = MagicMock()
        adapter = ExchangeIndexStoreAdapter(mock_db)
        assert inspect.iscoroutinefunction(adapter.save_index_constituent)

    def test_adapter_has_async_save_index_weight(self):
        """save_index_weight 应为 async 方法."""
        import inspect

        mock_db = MagicMock()
        adapter = ExchangeIndexStoreAdapter(mock_db)
        assert inspect.iscoroutinefunction(adapter.save_index_weight)

    def test_adapter_has_async_is_index_constituent_empty(self):
        """is_index_constituent_empty 应为 async 方法."""
        import inspect

        mock_db = MagicMock()
        adapter = ExchangeIndexStoreAdapter(mock_db)
        assert inspect.iscoroutinefunction(adapter.is_index_constituent_empty)


class TestSaveIndexConstituent:
    """save_index_constituent 方法测试."""

    def test_empty_list_returns_zero_without_db(self):
        """空列表应直接返回 0，不操作数据库."""
        mock_db = MagicMock()
        adapter = ExchangeIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.save_index_constituent([]))
        assert result == 0
        mock_db.session.assert_not_called()

    def test_all_none_in_date_filtered_returns_zero(self):
        """in_date 为 None 的记录应被过滤，全空则返回 0."""
        mock_db = MagicMock()
        adapter = ExchangeIndexStoreAdapter(mock_db)
        records = [
            IndexConstituent(
                index_code="000300.SH",
                con_code="600000.SH",
                in_date=None,
                out_date=None,
                index_name=None,
            )
        ]
        result = asyncio.run(adapter.save_index_constituent(records))
        assert result == 0
        mock_db.session.assert_not_called()

    def test_saves_constituents_and_returns_count(self):
        """应 UPSERT 成分股记录并返回写入条数."""
        mock_db, mock_session = _make_mock_db()
        adapter = ExchangeIndexStoreAdapter(mock_db)
        records = [
            IndexConstituent(
                index_code="000300.SH",
                con_code="600000.SH",
                in_date="20240101",
                out_date=None,
                index_name="沪深300",
            ),
            IndexConstituent(
                index_code="000300.SH",
                con_code="000001.SZ",
                in_date="20240101",
                out_date=None,
                index_name="沪深300",
            ),
        ]
        result = asyncio.run(adapter.save_index_constituent(records))
        assert result == 2
        mock_db.session.assert_called_once()
        mock_session.execute.assert_called()

    def test_intra_batch_dedup_by_conflict_key(self):
        """批内按 (index_code, con_code, in_date) 冲突键去重，保留最后."""
        mock_db, mock_session = _make_mock_db()
        adapter = ExchangeIndexStoreAdapter(mock_db)
        records = [
            IndexConstituent("000300.SH", "600000.SH", "20240101", None, "旧名"),
            IndexConstituent("000300.SH", "600000.SH", "20240101", None, "新名"),
        ]
        result = asyncio.run(adapter.save_index_constituent(records))
        assert result == 1


class TestSaveIndexWeight:
    """save_index_weight 方法测试."""

    def test_empty_list_returns_zero_without_db(self):
        """空列表应直接返回 0，不操作数据库."""
        mock_db = MagicMock()
        adapter = ExchangeIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.save_index_weight([]))
        assert result == 0
        mock_db.session.assert_not_called()

    def test_none_trade_date_filtered_returns_zero(self):
        """trade_date 为 None 的记录应被过滤，全空则返回 0."""
        mock_db = MagicMock()
        adapter = ExchangeIndexStoreAdapter(mock_db)
        records = [
            IndexWeight(
                index_code="000300.SH",
                con_code="600000.SH",
                trade_date=None,
                total_share=None,
                free_share_ratio=None,
                calc_share=None,
                weight_factor=None,
                weight=None,
                close=None,
            )
        ]
        result = asyncio.run(adapter.save_index_weight(records))
        assert result == 0
        mock_db.session.assert_not_called()

    def test_saves_weights_and_returns_count(self):
        """应 UPSERT 权重记录并返回写入条数."""
        mock_db, mock_session = _make_mock_db()
        adapter = ExchangeIndexStoreAdapter(mock_db)
        records = [
            IndexWeight(
                index_code="000300.SH",
                con_code="600000.SH",
                trade_date="20240115",
                total_share=1e9,
                free_share_ratio=80.0,
                calc_share=8e8,
                weight_factor=1.0,
                weight=2.5,
                close=10.5,
            )
        ]
        result = asyncio.run(adapter.save_index_weight(records))
        assert result == 1
        mock_db.session.assert_called_once()
        mock_session.execute.assert_called()


class TestIsIndexConstituentEmpty:
    """is_index_constituent_empty 方法测试."""

    def test_returns_true_when_count_zero(self):
        """表空（count=0）应返回 True."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_session.execute.return_value = mock_result

        adapter = ExchangeIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.is_index_constituent_empty())
        assert result is True

    def test_returns_false_when_count_positive(self):
        """表非空（count>0）应返回 False."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        mock_session.execute.return_value = mock_result

        adapter = ExchangeIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.is_index_constituent_empty())
        assert result is False

    def test_returns_true_on_sqlalchemy_error(self):
        """SQLAlchemy 错误时应返回 True（首次同步分支安全默认）."""
        from sqlalchemy.exc import SQLAlchemyError

        mock_db, mock_session = _make_mock_db()
        mock_session.execute.side_effect = SQLAlchemyError("db down")

        adapter = ExchangeIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.is_index_constituent_empty())
        assert result is True


class TestUpsertErrorHandling:
    """UPSERT 异常应包装为 CacheError."""

    def test_constituent_upsert_raises_cache_error(self):
        """save_index_constituent 遇 SQLAlchemyError 应抛 CacheError."""
        from sqlalchemy.exc import SQLAlchemyError

        mock_db, mock_session = _make_mock_db()
        mock_session.execute.side_effect = SQLAlchemyError("write failed")

        adapter = ExchangeIndexStoreAdapter(mock_db)
        records = [
            IndexConstituent("000300.SH", "600000.SH", "20240101", None, None)
        ]
        with pytest.raises(CacheError):
            asyncio.run(adapter.save_index_constituent(records))
