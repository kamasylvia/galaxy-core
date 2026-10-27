import sys
import types
import importlib
import pytest
import pandas as pd
# fake openbb_app.core.registry.register_widget (identity decorator)
reg_mod = types.ModuleType("openbb_app.core.registry")


def register_widget(*a, **k):
    def deco(fn):
        return fn

    return deco


reg_mod.register_widget = register_widget
sys.modules["openbb_app.core.registry"] = reg_mod
# fake mysharelib.tools (normalize_symbol + get_valid_date)
ms_mod = types.ModuleType("mysharelib")
ms_tools = types.ModuleType("mysharelib.tools")


def _normalize_symbol(symbol):
    return (symbol, symbol, "SH")


def _get_valid_date(v):
    return pd.Timestamp(v).date()


ms_tools.normalize_symbol = _normalize_symbol
ms_tools.get_valid_date = _get_valid_date
ms_mod.tools = ms_tools
sys.modules["mysharelib"] = ms_mod
sys.modules["mysharelib.tools"] = ms_tools

# import the module under test
tv = importlib.import_module("openbb_app.routes.tradingview")


def _bars(df):
    """DataFrame -> AmazingDataSource bar list."""
    out = []
    for ts, row in df.iterrows():
        out.append(
            {
                "date": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
                "amount": None,
                "interval": "1d",
            }
        )
    return out


def _patch_bars(monkeypatch, df):
    bars = _bars(df)

    def fake_get(self, symbol, start_date, end_date, interval="1d"):
        return bars

    monkeypatch.setattr(
        "openbb_app.core.amazingdata_source.AmazingDataSource.get_historical_data",
        fake_get,
    )


@pytest.mark.asyncio
async def test_provider_returns_none_results_in_no_data(monkeypatch):
    monkeypatch.setattr(
        "openbb_app.core.amazingdata_source.AmazingDataSource.get_historical_data",
        lambda self, *a, **k: [],
    )
    res = await tv.get_history(symbol="AAA", resolution="D", from_time=1577836800, to_time=1577923200)
    assert res == {"s": "no_data"}


@pytest.mark.asyncio
async def test_daily_resolution_returns_ok_and_ohlcv(monkeypatch):
    idx = pd.date_range("2020-01-01", periods=3, freq="D")
    df = pd.DataFrame({
        "open": [1, 2, 3],
        "high": [1.5, 2.5, 3.5],
        "low": [0.8, 1.8, 2.8],
        "close": [1.2, 2.2, 3.2],
        "volume": [100, 200, 300],
    }, index=idx)

    _patch_bars(monkeypatch, df)
    from_ts = int(pd.Timestamp("2020-01-01").timestamp())
    to_ts = int(pd.Timestamp("2020-01-03 23:59:59").timestamp())
    res = await tv.get_history(symbol="AAA", resolution="D", from_time=from_ts, to_time=to_ts)

    assert res["s"] == "ok"
    assert len(res["t"]) == 3
    assert len(res["o"]) == 3
    assert len(res["h"]) == 3
    assert len(res["l"]) == 3
    assert len(res["c"]) == 3
    assert len(res["v"]) == 3
    assert res["o"][0] == float(df["open"].iloc[0])
    assert res["c"][-1] == float(df["close"].iloc[-1])
