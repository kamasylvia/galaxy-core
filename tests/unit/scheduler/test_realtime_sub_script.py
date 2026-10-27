"""realtime_sub.py 源码级回归测试.

背景(2026-10-27,见 .work/TODO.md):
1. SDK pydantic Kline 时间字段是 ``kline_time``(非 trade_time),缺失回退会把
   100% 的实时 bar 丢弃;
2. 用户裁决:realtime 只订沪深 ETF(51x/56x/58x SH + 15x SZ)、窗口 14:00-15:10、
   周期只订 min1/min5(quota 100G/年);ETF 的 security_type 按交易所映射
   SH_ETF/SZ_ETF(与日线链分类一致)。
"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "realtime_sub.py"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _load_module():
    spec = importlib.util.spec_from_file_location("realtime_sub_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_kline_time_fallback_present():
    src = _source()
    assert 'd.get("kline_time")' in src, (
        "_upsert_batch 缺少 kline_time 回退:SDK pydantic Kline 时间字段是 "
        "kline_time 而非 trade_time,缺失会把 100% 的实时 bar 丢弃"
    )


def test_periods_etf_ruling():
    src = _source()
    assert 'PERIODS = ["min1", "min5"]' in src, "周期应为 min1/min5(2026-10-27 裁决)"


def test_universe_etf_only():
    src = _source()
    assert "symbol LIKE '51%'" in src and "symbol LIKE '15%'" in src, (
        "universe 应为沪深 ETF-only(51x/56x/58x SH + 15x SZ,2026-10-27 裁决)"
    )
    assert "NOT LIKE" not in src, "旧的「排除法」股票过滤已废弃,不得回潮(过滤不全混入 ETF)"


def test_etf_security_type_mapping():
    from galaxy_core.domain.value_objects import SecurityType

    mod = _load_module()
    assert mod._etf_security_type("510300.SH") is SecurityType.SH_ETF
    assert mod._etf_security_type("563330.SH") is SecurityType.SH_ETF
    assert mod._etf_security_type("159915.SZ") is SecurityType.SZ_ETF


def test_upsert_batch_maps_kline_time(monkeypatch):
    """pydantic 形态 bar(带 kline_time)应被转换为 KlineBar 而非丢弃。"""
    from datetime import datetime
    from types import SimpleNamespace

    from galaxy_core.domain.value_objects import SecurityType

    mod = _load_module()
    captured = {}

    class StubAdapter:
        def __init__(self, mgr):
            pass

        async def save_kline(self, bars, interval):
            captured["bars"] = bars
            return len(bars)

    import galaxy_core.database.core.async_connection as conn_mod
    import galaxy_core.database.services.adapters.kline_store_adapter as adapter_mod

    class StubMgr:
        def initialize(self):
            pass

        async def close(self):
            pass

    monkeypatch.setattr(conn_mod.AsyncDatabaseManager, "initialize", lambda self: None)
    monkeypatch.setattr(conn_mod.AsyncDatabaseManager, "close", lambda self: None)
    monkeypatch.setattr(conn_mod.AsyncDatabaseManager, "__new__", lambda cls: StubMgr())
    monkeypatch.setattr(adapter_mod, "KlineStoreAdapter", StubAdapter)

    bar = SimpleNamespace(
        model_dump=lambda: {
            "code": "510300.SH",
            "kline_time": datetime(2026, 10, 27, 14, 1),
            "open": 4.1,
            "high": 4.2,
            "low": 4.0,
            "close": 4.1,
            "volume": 100000,
            "amount": 410000.0,
        }
    )

    import asyncio

    n = asyncio.run(mod._upsert_batch("min1", [bar]))

    assert n == 1
    kb = captured["bars"][0]
    assert kb.symbol == "510300.SH"
    assert kb.trade_time == datetime(2026, 10, 27, 14, 1)
    assert kb.is_final is False
    assert kb.security_type is SecurityType.SH_ETF


def test_upsert_batch_drops_bars_without_any_time(monkeypatch):
    """既无 kline_time 也无 trade_time 的脏 bar 仍应被丢弃(守卫保持)。"""
    from types import SimpleNamespace

    mod = _load_module()
    captured = {}

    class StubAdapter:
        def __init__(self, mgr):
            pass

        async def save_kline(self, bars, interval):
            captured["bars"] = bars
            return len(bars)

    import galaxy_core.database.core.async_connection as conn_mod
    import galaxy_core.database.services.adapters.kline_store_adapter as adapter_mod

    class StubMgr:
        def initialize(self):
            pass

        async def close(self):
            pass

    monkeypatch.setattr(conn_mod.AsyncDatabaseManager, "initialize", lambda self: None)
    monkeypatch.setattr(conn_mod.AsyncDatabaseManager, "close", lambda self: None)
    monkeypatch.setattr(conn_mod.AsyncDatabaseManager, "__new__", lambda cls: StubMgr())
    monkeypatch.setattr(adapter_mod, "KlineStoreAdapter", StubAdapter)

    bar = SimpleNamespace(model_dump=lambda: {"code": "510300.SH", "open": 4.1, "close": 4.1})

    import asyncio

    n = asyncio.run(mod._upsert_batch("min1", [bar]))

    assert n == 0
    assert captured["bars"] == []
