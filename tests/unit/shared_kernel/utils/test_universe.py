"""universe helper 单元测试.

验证 SDK 优先 + DB fallback 策略(AGENTS.md 2026-07-28 Bug 2)。
"""
from datetime import date
from unittest.mock import MagicMock, AsyncMock

import pytest

from galaxy_core.shared_kernel.utils.universe import (
    resolve_universe_with_fallback,
    _read_active_symbols_from_db,
)


def _make_ref_provider(codes: list[str] | None = None, exc: Exception | None = None):
    """造 mock reference_provider。codes=None 表示 SDK 返空。"""
    p = MagicMock()
    if exc is not None:
        p.get_hist_code_list = AsyncMock(side_effect=exc)
    else:
        p.get_hist_code_list = AsyncMock(return_value=codes or [])
    return p


def _make_db_manager(rows: list[tuple] | None = None, exc: Exception | None = None):
    """造 mock db_manager._engine.connect() async ctx。

    rows: SELECT 返回的行列表,如 [("600000.SH",), ("000001.SZ",)]
    """
    db = MagicMock()
    engine = MagicMock()

    mock_result = MagicMock()
    mock_result.all.return_value = rows or []

    mock_conn = MagicMock()
    if exc is not None:
        mock_conn.execute = AsyncMock(side_effect=exc)
    else:
        mock_conn.execute = AsyncMock(return_value=mock_result)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx.__aexit__ = AsyncMock(return_value=None)

    engine.connect = MagicMock(return_value=ctx)
    db._engine = engine
    return db


@pytest.mark.asyncio
async def test_sdk_non_empty_skips_db():
    """SDK 返非空时不查 DB。"""
    ref = _make_ref_provider(codes=["600000.SH", "000001.SZ"])
    db = _make_db_manager()

    result = await resolve_universe_with_fallback(
        reference_provider=ref,
        db_manager=db,
        security_type="EXTRA_STOCK_A",
        end_date=date(2026, 7, 28),
        local_path="/tmp/cache/",
    )

    assert sorted(result) == ["000001.SZ", "600000.SH"]
    # DB 未被查
    db._engine.connect.assert_not_called()


@pytest.mark.asyncio
async def test_sdk_empty_falls_back_to_db():
    """SDK 返空时从 stock_basic 读 codes。"""
    ref = _make_ref_provider(codes=[])
    db = _make_db_manager(rows=[("600000.SH",), ("000001.SZ",)])

    result = await resolve_universe_with_fallback(
        reference_provider=ref,
        db_manager=db,
        security_type="EXTRA_STOCK_A",
        end_date=date(2026, 7, 28),
        local_path="/tmp/cache/",
    )

    assert sorted(result) == ["000001.SZ", "600000.SH"]
    # DB 被查
    db._engine.connect.assert_called_once()


@pytest.mark.asyncio
async def test_db_empty_returns_empty():
    """SDK 返空 + DB 也空 → 返空。"""
    ref = _make_ref_provider(codes=[])
    db = _make_db_manager(rows=[])

    result = await resolve_universe_with_fallback(
        reference_provider=ref,
        db_manager=db,
        security_type="EXTRA_ETF",
        end_date=date(2026, 7, 28),
        local_path="/tmp/cache/",
    )

    assert result == []


@pytest.mark.asyncio
async def test_security_type_normalized_for_db_query():
    """EXTRA_STOCK_A_SH_SZ 在 DB fallback 时归一为 EXTRA_STOCK_A。

    因 stock_basic 表只存宽泛类型(EXTRA_STOCK_A / EXTRA_ETF / EXTRA_INDEX_A),
    子类型如 EXTRA_STOCK_A_SH_SZ 必须经 to_broad_security_type 归一才能查到。
    """
    ref = _make_ref_provider(codes=[])
    db = _make_db_manager(rows=[("600000.SH",)])

    result = await resolve_universe_with_fallback(
        reference_provider=ref,
        db_manager=db,
        security_type="EXTRA_STOCK_A_SH_SZ",
        end_date=date(2026, 7, 28),
        local_path="/tmp/cache/",
    )

    assert result == ["600000.SH"]
    # 验证 SQL 查询参数是宽泛类型(EXTRA_STOCK_A),非子类型
    call_args = db._engine.connect.return_value.__aenter__.return_value.execute.call_args
    stmt = call_args.args[0]
    # SQLAlchemy compiled 后的 bind params 含 EXTRA_STOCK_A
    compiled = stmt.compile()
    bind_values = compiled.params
    assert "EXTRA_STOCK_A" in str(bind_values)


@pytest.mark.asyncio
async def test_sdk_exception_falls_back_to_db():
    """SDK 抛异常时不阻断,继续 fallback DB。"""
    ref = _make_ref_provider(exc=RuntimeError("SDK timeout"))
    db = _make_db_manager(rows=[("600000.SH",)])

    result = await resolve_universe_with_fallback(
        reference_provider=ref,
        db_manager=db,
        security_type="EXTRA_STOCK_A",
        end_date=date(2026, 7, 28),
        local_path="/tmp/cache/",
    )

    assert result == ["600000.SH"]


@pytest.mark.asyncio
async def test_no_db_manager_skips_fallback():
    """CLI 场景: db_manager=None 时 SDK 返空直接返空,不报错。"""
    ref = _make_ref_provider(codes=[])

    result = await resolve_universe_with_fallback(
        reference_provider=ref,
        db_manager=None,
        security_type="EXTRA_ETF",
        end_date=date(2026, 7, 28),
        local_path="/tmp/cache/",
    )

    assert result == []


@pytest.mark.asyncio
async def test_read_active_symbols_handles_db_exception():
    """_read_active_symbols_from_db DB 异常时返空,不抛。"""
    db = _make_db_manager(exc=RuntimeError("DB down"))

    result = await _read_active_symbols_from_db(db, "EXTRA_STOCK_A")

    assert result == []
