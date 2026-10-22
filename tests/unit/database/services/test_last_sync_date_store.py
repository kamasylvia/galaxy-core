"""LastSyncDateStore 单元测试(Phase 03 03-02).

测试 (sync_type, scope_key) 模式的 get/set:
- get 无记录返 None(空表首次)
- get per-scope_key(symbol/index)
- get scope_key=None(全市场汇总 margin_summary)
- set UPSERT 新记录
- set UPSERT 已存在更新(不插重复)
- set + get roundtrip
- 三模式兼容:旧 K线(symbol, interval)数据不受 sync_type 模式影响

mock 策略:patch db_manager.session 为 async context manager,
session.execute 返受控结果。store 内部用 SQLAlchemy ORM,execute mock 即可。
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from galaxy_core.database.models.last_sync_date import LastSyncDate
from galaxy_core.database.services.last_sync_date_store import LastSyncDateStore
from galaxy_core.shared_kernel.exceptions import CacheError


def _make_store_with_mock_session():
    """构造 store + mock session,返 (store, session_mock)."""
    session_mock = MagicMock()
    session_mock.execute = AsyncMock()
    session_mock.add = MagicMock()
    session_mock.commit = AsyncMock()

    db_manager = MagicMock()

    @asynccontextmanager
    async def _session_ctx():
        yield session_mock

    db_manager.session = _session_ctx
    store = LastSyncDateStore(db_manager)
    return store, session_mock


def _mock_execute_returning(row_value):
    """让 session.execute 返一个 .first() 返回 row_value 的 result."""
    result = MagicMock()
    result.first.return_value = row_value
    return result


def _mock_execute_returning_rows(rows):
    """让 session.execute 返一个 .all() 返回 rows 的 result(批量查询用)."""
    result = MagicMock()
    result.all.return_value = rows
    return result


class TestGetLastSyncDate:
    """get_last_sync_date 行为."""

    def test_get_returns_none_when_no_record(self):
        store, session = _make_store_with_mock_session()
        session.execute.return_value = _mock_execute_returning(None)
        result = asyncio.run(store.get_last_sync_date("index_weight", "000300.SH"))
        assert result is None

    def test_get_returns_date_for_scope_key(self):
        store, session = _make_store_with_mock_session()
        session.execute.return_value = _mock_execute_returning((date(2024, 1, 15),))
        result = asyncio.run(store.get_last_sync_date("index_weight", "000300.SH"))
        assert result == date(2024, 1, 15)

    def test_get_returns_date_for_global_null_scope(self):
        """scope_key=None(全市场汇总 margin_summary)."""
        store, session = _make_store_with_mock_session()
        session.execute.return_value = _mock_execute_returning((date(2024, 1, 15),))
        result = asyncio.run(store.get_last_sync_date("margin_summary", None))
        assert result == date(2024, 1, 15)

    def test_get_sqlalchemy_error_wraps_cacherror(self):
        from sqlalchemy.exc import SQLAlchemyError

        store, session = _make_store_with_mock_session()
        session.execute.side_effect = SQLAlchemyError("conn lost")
        with pytest.raises(CacheError):
            asyncio.run(store.get_last_sync_date("index_weight", "000300.SH"))


class TestGetLastSyncDatesBatch:
    """get_last_sync_dates_batch 批量查询行为(2026-08-01 新增).

    替代 N 次 get_last_sync_date,消除 fundflow per-symbol 表 5200+ 次串行查询。
    """

    def test_batch_returns_dict_for_found_keys(self):
        """查到的 key 返回 {scope_key: date}。"""
        store, session = _make_store_with_mock_session()
        session.execute.return_value = _mock_execute_returning_rows(
            [("000300.SH", date(2024, 1, 15)), ("000905.SH", date(2024, 1, 16))]
        )
        result = asyncio.run(
            store.get_last_sync_dates_batch("index_weight", ["000300.SH", "000905.SH"])
        )
        assert result == {
            "000300.SH": date(2024, 1, 15),
            "000905.SH": date(2024, 1, 16),
        }

    def test_batch_empty_keys_returns_empty_dict(self):
        """空 scope_keys 返 {}(不发 SQL)。"""
        store, session = _make_store_with_mock_session()
        result = asyncio.run(store.get_last_sync_dates_batch("index_weight", []))
        assert result == {}
        session.execute.assert_not_called()

    def test_batch_missing_keys_excluded(self):
        """无记录的 key 不包含在返回 dict 中。"""
        store, session = _make_store_with_mock_session()
        session.execute.return_value = _mock_execute_returning_rows(
            [("000300.SH", date(2024, 1, 15))]
        )
        result = asyncio.run(
            store.get_last_sync_dates_batch(
                "index_weight", ["000300.SH", "999999.SH"]  # 999999 无记录
            )
        )
        assert result == {"000300.SH": date(2024, 1, 15)}
        assert "999999.SH" not in result

    def test_batch_sqlalchemy_error_wraps_cacherror(self):
        from sqlalchemy.exc import SQLAlchemyError

        store, session = _make_store_with_mock_session()
        session.execute.side_effect = SQLAlchemyError("conn lost")
        with pytest.raises(CacheError):
            asyncio.run(
                store.get_last_sync_dates_batch("index_weight", ["000300.SH"])
            )


class TestSetLastSyncDate:
    """set_last_sync_date UPSERT 行为."""

    def test_set_calls_execute_with_upsert_stmt(self):
        """set 应调 session.execute(UPSERT stmt,D-24 per-symbol partial index)."""
        store, session = _make_store_with_mock_session()
        asyncio.run(
            store.set_last_sync_date("long_hu_bang", "600000.SH", date(2024, 1, 15))
        )
        session.execute.assert_called_once()
        # D-24:per-symbol 用 (sync_type, scope_key) + WHERE scope_key IS NOT NULL
        stmt = session.execute.call_args.args[0]
        compiled = str(
            stmt.compile(compile_kwargs={"literal_binds": True})
        )
        assert "ON CONFLICT" in compiled
        assert "long_hu_bang" in compiled
        # partial index WHERE 子句
        assert "scope_key IS NOT NULL" in compiled

    def test_set_global_null_scope(self):
        """D-24:scope_key=None 全局表用 partial index(WHERE scope_key IS NULL)."""
        store, session = _make_store_with_mock_session()
        asyncio.run(
            store.set_last_sync_date("margin_summary", None, date(2024, 1, 15))
        )
        session.execute.assert_called_once()
        stmt = session.execute.call_args.args[0]
        compiled = str(
            stmt.compile(compile_kwargs={"literal_binds": True})
        )
        # 全局表 ON CONFLICT (sync_type) WHERE scope_key IS NULL
        assert "ON CONFLICT" in compiled
        assert "scope_key IS NULL" in compiled

    def test_set_sqlalchemy_error_wraps_cacherror(self):
        from sqlalchemy.exc import SQLAlchemyError

        store, session = _make_store_with_mock_session()
        session.execute.side_effect = SQLAlchemyError("conn lost")
        with pytest.raises(CacheError):
            asyncio.run(
                store.set_last_sync_date("index_weight", "000300.SH", date(2024, 1, 15))
            )


class TestThreeModeCompatibility:
    """三模式 CHECK 兼容性 — model 层断言."""

    def test_model_has_sync_type_scope_key_columns(self):
        """LastSyncDate model 应含 sync_type + scope_key 列(Phase 03 新增)."""
        cols = {c.name for c in LastSyncDate.__table__.columns}
        assert "sync_type" in cols
        assert "scope_key" in cols

    def test_model_symbol_nullable_for_three_mode(self):
        """三模式兼容:symbol 应改为 nullable(Phase 1&2 模式无 symbol)."""
        symbol_col = LastSyncDate.__table__.columns["symbol"]
        assert symbol_col.nullable is True

    def test_partial_unique_indexes_live_in_db_layer(self):
        """(2026-08-26 nocodb 回迁)2 个 partial unique index 由 DB 层 P3 补建,
        ORM 不声明索引(与性能索引同一策略)。

        D-24 语义(uq_last_sync_date_sync_type_global/scoped)仍由 DB 保证,
        本测试确认 ORM 侧不重复声明以免 init 时冲突。
        """
        index_names = {idx.name for idx in LastSyncDate.__table__.indexes}
        assert "uq_last_sync_date_sync_type_global" not in index_names
        assert "uq_last_sync_date_sync_type_scoped" not in index_names

    def test_model_three_mode_columns_nullable(self):
        """(2026-08-26 nocodb 回迁)三模式列保持 nullable,K线/财务/Phase 1&2 兼容。

        旧 CHECK 约束随整库重建消亡(nocodb 形态无此约束),三模式语义
        由 store 写入逻辑保证(单模式写入时其余列为 NULL)。
        """
        cols = {c.name: c for c in LastSyncDate.__table__.columns}
        for c in ("sync_type", "data_type", "interval", "symbol", "scope_key"):
            assert c in cols
            assert cols[c].nullable is True
