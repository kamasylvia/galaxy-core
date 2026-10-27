"""realtime_sub.py 源码级回归测试.

背景(2026-10-27 实测定因,见 .work/TODO.md):SDK pydantic Kline 的时间字段
是 ``kline_time``,而 ``_upsert_batch`` 此前只取 ``trade_time`` → 「无时间戳」
守卫把 100% 的 bar 丢弃,flush 日志恒「0 bars」、实时分钟线落库全灭。
推送通道本身一直正常(含互踢修复后的常规到达)。
"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "realtime_sub.py"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_kline_time_fallback_present():
    src = _source()
    assert 'd.get("kline_time")' in src, (
        "_upsert_batch 缺少 kline_time 回退:SDK pydantic Kline 时间字段是 "
        "kline_time 而非 trade_time,缺失会把 100% 的实时 bar 丢弃"
    )


def test_kline_periods_unchanged():
    src = _source()
    assert 'PERIODS = ["min1", "min3", "min5", "min10", "min15", "min30", "min60", "min120"]' in src


def _load_module():
    spec = importlib.util.spec_from_file_location("realtime_sub_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_upsert_batch_maps_kline_time(monkeypatch):
    """pydantic 形态 bar(带 kline_time)应被转换为 KlineBar 而非丢弃。"""
    from datetime import datetime
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

    bar = SimpleNamespace(
        model_dump=lambda: {
            "code": "600000.SH",
            "kline_time": datetime(2026, 10, 27, 10, 32),
            "open": 9.6,
            "high": 9.7,
            "low": 9.5,
            "close": 9.6,
            "volume": 1000,
            "amount": 9600.0,
        }
    )

    import asyncio

    n = asyncio.run(mod._upsert_batch("min1", [bar]))

    assert n == 1
    kb = captured["bars"][0]
    assert kb.symbol == "600000.SH"
    assert kb.trade_time == datetime(2026, 10, 27, 10, 32)
    assert kb.is_final is False


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

    bar = SimpleNamespace(model_dump=lambda: {"code": "600000.SH", "open": 9.6, "close": 9.6})

    import asyncio

    n = asyncio.run(mod._upsert_batch("min1", [bar]))

    assert n == 0
    assert captured["bars"] == []
