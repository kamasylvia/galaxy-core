"""Benchmark tests for vectorized vs iterrows performance.

使用 pytest-benchmark 对比向量化实现与旧 iterrows 实现的性能差异。
运行方式: pytest tests/unit/benchmark_vectorization.py --benchmark-only
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime

from galaxy_core.database.services.kline import (
    extract_row_values,
    parse_trade_time,
)
from galaxy_core.application.scheduler.reference_data_sync_job import ReferenceDataSyncJob


# ============================================================================
# Helpers: iterrows 版本（旧实现）
# ============================================================================


def _iterrows_kline_records(df: pd.DataFrame) -> list[dict]:
    """旧 iterrows 版本的 kline record 提取."""
    records = []
    for _, row in df.iterrows():
        trade_time = parse_trade_time(row.name)
        values = extract_row_values(row)
        record = {
            "symbol": "TEST.SH",
            "trade_time": trade_time,
            "open": values["open"],
            "high": values["high"],
            "low": values["low"],
            "close": values["close"],
            "volume": values["volume"],
            "amount": values["amount"],
            "security_type": "stock",
        }
        records.append(record)
    return records


def _iterrows_stock_basic_records(df: pd.DataFrame, security_type: str) -> list[dict]:
    """旧 iterrows 版本的 stock_basic record 提取."""
    records = []
    for _, row in df.iterrows():
        code = row.get("MARKET_CODE") or row.get("code")
        if not code:
            continue
        list_date = ReferenceDataSyncJob._parse_date(row.get("LISTDATE"))
        record = {
            "symbol": code,
            "security_name": row.get("SECURITY_NAME"),
            "comp_name": row.get("COMP_NAME"),
            "pinyin": row.get("PINYIN"),
            "list_date": list_date,
            "delist_date": ReferenceDataSyncJob._parse_date(row.get("DELISTDATE")),
            "security_type": security_type,
        }
        records.append(record)
    return records


def _iterrows_stock_status_records(code: str, df: pd.DataFrame) -> list[dict]:
    """旧 iterrows 版本的 stock_status record 提取."""
    records = []
    for _, row in df.iterrows():
        trade_date = ReferenceDataSyncJob._parse_date(row.get("TRADE_DATE"))
        if trade_date is None:
            continue
        records.append(
            {
                "symbol": code,
                "trade_date": trade_date,
                "preclose": ReferenceDataSyncJob._to_float(row.get("PRECLOSE")),
                "high_limited": ReferenceDataSyncJob._to_float(row.get("HIGH_LIMITED")),
                "low_limited": ReferenceDataSyncJob._to_float(row.get("LOW_LIMITED")),
                "is_st_sec": ReferenceDataSyncJob._to_bool(row.get("IS_ST_SEC")),
                "is_susp_sec": ReferenceDataSyncJob._to_bool(row.get("IS_SUSP_SEC")),
                "is_xr_sec": ReferenceDataSyncJob._to_bool(row.get("IS_XR_SEC")),
                "is_wd_sec": ReferenceDataSyncJob._to_bool(row.get("IS_WD_SEC")),
            }
        )
    return records


# ============================================================================
# Fixtures: DataFrame generators
# ============================================================================


@pytest.fixture
def kline_day_df():
    """Generate 5000-row daily K-line DataFrame."""
    n = 5000
    dates = pd.bdate_range("2015-01-01", periods=n)
    np.random.seed(42)
    base = 10.0
    returns = np.random.randn(n) * 0.02
    prices = base * np.cumprod(1 + returns)
    return pd.DataFrame(
        {
            "open": prices * (1 + np.random.randn(n) * 0.005),
            "high": prices * (1 + np.abs(np.random.randn(n) * 0.01)),
            "low": prices * (1 - np.abs(np.random.randn(n) * 0.01)),
            "close": prices,
            "volume": np.random.randint(100000, 10000000, n).astype(float),
            "amount": np.random.uniform(1e6, 1e8, n),
        },
        index=dates,
    )


@pytest.fixture
def kline_min1_df():
    """Generate 5000-row minute K-line DataFrame."""
    n = 5000
    dates = pd.date_range("2025-01-15 09:30:00", periods=n, freq="min")
    np.random.seed(42)
    base = 10.0
    returns = np.random.randn(n) * 0.001
    prices = base * np.cumprod(1 + returns)
    return pd.DataFrame(
        {
            "open": prices * (1 + np.random.randn(n) * 0.0005),
            "high": prices * (1 + np.abs(np.random.randn(n) * 0.001)),
            "low": prices * (1 - np.abs(np.random.randn(n) * 0.001)),
            "close": prices,
            "volume": np.random.randint(1000, 100000, n).astype(float),
            "amount": np.random.uniform(1e4, 1e6, n),
            "kline_time": dates.strftime("%Y%m%d%H%M%S"),
        },
        index=dates,
    )


@pytest.fixture
def stock_basic_df():
    """Generate 5000-row stock_basic DataFrame."""
    n = 5000
    codes = [f"{600000 + i:06d}.SH" for i in range(n)]
    return pd.DataFrame(
        {
            "MARKET_CODE": codes,
            "SECURITY_NAME": [f"股票{i}" for i in range(n)],
            "COMP_NAME": [f"公司{i}" for i in range(n)],
            "PINYIN": [f"GP{i}" for i in range(n)],
            "LISTDATE": [f"20{10 + (i % 15):02d}0101" for i in range(n)],
            "DELISTDATE": [None] * n,
        }
    )


@pytest.fixture
def stock_status_df():
    """Generate 5000-row stock_status DataFrame."""
    n = 5000
    return pd.DataFrame(
        {
            "TRADE_DATE": [f"202501{(i % 28) + 1:02d}" for i in range(n)],
            "PRECLOSE": np.random.uniform(5.0, 50.0, n),
            "HIGH_LIMITED": np.random.uniform(5.5, 55.0, n),
            "LOW_LIMITED": np.random.uniform(4.5, 45.0, n),
            "IS_ST_SEC": np.random.choice([0, 1], n, p=[0.95, 0.05]),
            "IS_SUSP_SEC": np.zeros(n, dtype=int),
            "IS_XR_SEC": np.zeros(n, dtype=int),
            "IS_WD_SEC": np.zeros(n, dtype=int),
        }
    )


# ============================================================================
# Benchmark tests
# ============================================================================


class TestBenchmarkKlineSave:
    """Benchmark kline save: iterrows vs vectorized."""

    def test_benchmark_kline_day_iterrows(self, benchmark, kline_day_df):
        """Benchmark iterrows kline day."""
        result = benchmark(_iterrows_kline_records, kline_day_df)
        assert len(result) == 5000

    def test_benchmark_kline_day_vectorized(self, benchmark, kline_day_df):
        """Benchmark vectorized kline day."""
        from galaxy_core.database.services.kline import (
            parse_trade_time_vectorized,
            extract_records_vectorized,
        )

        def _vectorized_kline_records(df):
            time_col = df.index
            parsed, errors = parse_trade_time_vectorized(time_col)
            ohlcv_records = extract_records_vectorized(df[["open", "high", "low", "close", "volume", "amount"]])
            for rec, tt in zip(ohlcv_records, parsed):
                rec["symbol"] = "TEST.SH"
                rec["trade_time"] = tt
                rec["security_type"] = "stock"
            return ohlcv_records

        result = benchmark(_vectorized_kline_records, kline_day_df)
        assert len(result) == 5000

    def test_benchmark_kline_min1_iterrows(self, benchmark, kline_min1_df):
        """Benchmark iterrows kline min1."""
        result = benchmark(_iterrows_kline_records, kline_min1_df)
        assert len(result) == 5000

    def test_benchmark_kline_min1_vectorized(self, benchmark, kline_min1_df):
        """Benchmark vectorized kline min1."""
        from galaxy_core.database.services.kline import (
            parse_trade_time_vectorized,
            extract_records_vectorized,
        )

        def _vectorized_kline_records(df):
            if "kline_time" in df.columns:
                time_col = df["kline_time"]
                fallback = df.index
            else:
                time_col = df.index
                fallback = None
            parsed, errors = parse_trade_time_vectorized(time_col, fallback_series=fallback)
            ohlcv_records = extract_records_vectorized(df[["open", "high", "low", "close", "volume", "amount"]])
            for rec, tt in zip(ohlcv_records, parsed):
                rec["symbol"] = "TEST.SH"
                rec["trade_time"] = tt
                rec["security_type"] = "stock"
            return ohlcv_records

        result = benchmark(_vectorized_kline_records, kline_min1_df)
        assert len(result) == 5000


class TestBenchmarkStockBasic:
    """Benchmark stock_basic: iterrows vs vectorized."""

    def test_benchmark_stock_basic_iterrows(self, benchmark, stock_basic_df):
        """Benchmark iterrows stock_basic."""
        result = benchmark(_iterrows_stock_basic_records, stock_basic_df, "EXTRA_ETF")
        assert len(result) == 5000

    def test_benchmark_stock_basic_vectorized(self, benchmark, stock_basic_df):
        """Benchmark vectorized stock_basic."""
        result = benchmark(
            ReferenceDataSyncJob._parse_stock_basic_records,
            stock_basic_df,
            "EXTRA_ETF",
        )
        assert len(result) == 5000


class TestBenchmarkStockStatus:
    """Benchmark stock_status: iterrows vs vectorized."""

    def test_benchmark_stock_status_iterrows(self, benchmark, stock_status_df):
        """Benchmark iterrows stock_status."""
        result = benchmark(_iterrows_stock_status_records, "600000.SH", stock_status_df)
        assert len(result) > 0

    def test_benchmark_stock_status_vectorized(self, benchmark, stock_status_df):
        """Benchmark vectorized stock_status."""
        result = benchmark(
            ReferenceDataSyncJob._parse_stock_status_records,
            "600000.SH",
            stock_status_df,
        )
        assert len(result) > 0
