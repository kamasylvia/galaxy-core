"""realtime_sub.py 源码级回归测试.

背景(2026-10-27,见 .work/TODO.md):
1. SDK pydantic Kline 时间字段是 ``kline_time``(非 trade_time),缺失回退会把
   100% 的实时 bar 丢弃;
2. 订阅三要素全部配置化(公开发布用户可配,settings.toml [scheduler]):
   universe=realtime_sub_universe_prefixes(默认沪深 ETF 前缀)、
   周期=realtime_sub_periods(默认 min1/min5)、窗口=realtime_sub_start/end
   (默认 14:00-15:10);security_type 走 infer_security_type 通用推断,
   任意 universe 配置都正确标注。
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


def test_periods_from_config():
    """周期必须配置化:脚本读 realtime_sub_periods,默认 min1/min5."""
    src = _source()
    assert 'list(_cfg("realtime_sub_periods"' in src, "PERIODS 必须来自配置,不得写死"
    assert 'realtime_sub_periods = ["min1", "min5"]' in _settings(), (
        "settings.toml 缺 realtime_sub_periods 默认值"
    )


def test_universe_from_config():
    """universe 必须配置化:脚本读 realtime_sub_universe_prefixes(集合选择,非排除法)."""
    src = _source()
    assert '_cfg("realtime_sub_universe_prefixes"' in src, "universe 必须来自配置,不得写死"
    assert "LIKE ANY($1)" in src, "前缀过滤应走参数化 LIKE ANY"
    assert 'realtime_sub_universe_prefixes = ["51%", "56%", "58%", "15%"]' in _settings(), (
        "settings.toml 缺 universe 前缀默认值(沪深 ETF 全集)"
    )


def test_security_type_via_infer():
    """security_type 走 infer_security_type 通用推断(任意 universe 配置自适应)."""
    src = _source()
    assert "infer_security_type" in src, "security_type 必须走 infer_security_type"
    assert "_etf_security_type" not in src, "写死的 ETF 映射应已删除"

    from galaxy_core.domain.value_objects import SecurityType
    from galaxy_core.shared_kernel.utils.symbol_type_inference import (
        infer_security_type,
    )

    mod = _load_module()
    assert mod.security_type_for("510300.SH") is SecurityType.SH_ETF
    assert mod.security_type_for("159915.SZ") is SecurityType.SZ_ETF
    assert mod.security_type_for("600000.SH") is SecurityType.SH_A


def _settings() -> str:
    return (Path(__file__).resolve().parents[3] / "config" / "settings.toml").read_text(
        encoding="utf-8"
    )


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
