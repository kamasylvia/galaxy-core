#!/usr/bin/env python3
"""Benchmark the K-line sync orchestrator hot path for a target checkout.

This script runs a controlled synthetic workload against
`application/kline/sync_orchestrator.py` from any target root. It avoids real
API/DB dependencies by loading the module directly from source and stubbing the
external services it imports.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
import time
import types
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd


@dataclass
class BenchmarkConfig:
    symbols: int
    ranges_per_symbol: int
    rows_per_range: int
    sleep_ms: float
    repeats: int
    warmup: int
    max_concurrent_values: list[int]
    mode: str


@dataclass
class StubState:
    missing_ranges_by_symbol: dict[str, list[tuple[date, date]]]
    db_data: dict[str, pd.DataFrame]


def _load_module(module_name: str, file_path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _install_vendor_stubs() -> None:
    if "AmazingData" not in sys.modules:
        period = types.SimpleNamespace(
            min1=types.SimpleNamespace(value=10000),
            min3=types.SimpleNamespace(value=10001),
            min5=types.SimpleNamespace(value=10002),
            min10=types.SimpleNamespace(value=10003),
            min15=types.SimpleNamespace(value=10004),
            min30=types.SimpleNamespace(value=10005),
            min60=types.SimpleNamespace(value=10006),
            min120=types.SimpleNamespace(value=10007),
            day=types.SimpleNamespace(value=10008),
            week=types.SimpleNamespace(value=10009),
            month=types.SimpleNamespace(value=10010),
            season=types.SimpleNamespace(value=10011),
            year=types.SimpleNamespace(value=10012),
        )
        sys.modules["AmazingData"] = types.SimpleNamespace(
            constant=types.SimpleNamespace(Period=period),
            login=lambda **kwargs: None,
            logout=lambda *args, **kwargs: None,
            BaseData=lambda: types.SimpleNamespace(get_calendar=lambda *args, **kwargs: []),
            InfoData=lambda: types.SimpleNamespace(),
            MarketData=lambda calendar: types.SimpleNamespace(query_kline=lambda **kwargs: {}),
        )

    if "akshare" not in sys.modules:
        sys.modules["akshare"] = types.SimpleNamespace()


def _install_dependency_stubs(state: StubState, config: BenchmarkConfig) -> None:
    def ensure_package(name: str) -> None:
        if name not in sys.modules:
            module = types.ModuleType(name)
            module.__path__ = []
            sys.modules[name] = module

    for package_name in [
        "galaxy_db_sync",
        "galaxy_db_sync.amazing_data",
        "galaxy_db_sync.amazing_data.api",
        "galaxy_db_sync.database",
        "galaxy_db_sync.database.services",
        "galaxy_db_sync.shared_kernel",
        "galaxy_db_sync.shared_kernel.utils",
    ]:
        ensure_package(package_name)

    class BenchmarkAmazingDataClient:
        def logout(self, *args: Any, **kwargs: Any) -> None:
            del args, kwargs

        def query_kline(
            self,
            code_list: list[str],
            begin_date: int,
            end_date: int,
            interval: int | None = None,
            begin_time: int | None = None,
            end_time: int | None = None,
            period: int | None = None,
        ) -> dict[str, pd.DataFrame]:
            del end_date, interval, period, begin_time, end_time
            time.sleep(config.sleep_ms / 1000)
            return {
                code: _make_frame(code, begin_date, config.rows_per_range)
                for code in code_list
            }

        async def query_kline_async(
            self,
            code_list: list[str],
            begin_date: int,
            end_date: int,
            interval: int,
            begin_time: int | None = None,
            end_time: int | None = None,
        ) -> dict[str, pd.DataFrame]:
            return await asyncio.to_thread(
                self.query_kline,
                code_list=code_list,
                begin_date=begin_date,
                end_date=end_date,
                interval=interval,
                begin_time=begin_time,
                end_time=end_time,
            )

    client_module = types.ModuleType("galaxy_db_sync.amazing_data.api.client")
    client_module.amazing_data_client = BenchmarkAmazingDataClient()
    sys.modules[client_module.__name__] = client_module

    @dataclass
    class CompletenessResult:
        is_complete: bool
        missing_count: int
        total_count: int
        coverage_ratio: float
        missing_ranges: list[tuple[date, date]]
        check_method: str

    def check(symbol: str, interval: str, start_date: str, end_date: str) -> CompletenessResult:
        del interval, start_date, end_date
        missing_ranges = state.missing_ranges_by_symbol[symbol]
        return CompletenessResult(
            is_complete=False,
            missing_count=len(missing_ranges),
            total_count=len(missing_ranges) + 1,
            coverage_ratio=1 / (len(missing_ranges) + 1),
            missing_ranges=missing_ranges,
            check_method="benchmark",
        )

    completeness_module = types.ModuleType(
        "galaxy_db_sync.database.services.kline_completeness_checker"
    )
    completeness_module.CompletenessResult = CompletenessResult
    completeness_module.kline_completeness_checker = types.SimpleNamespace(check=check)
    sys.modules[completeness_module.__name__] = completeness_module

    empty_query_module = types.ModuleType("galaxy_db_sync.database.services.empty_query")
    empty_query_module.empty_query_service = types.SimpleNamespace(
        is_confirmed_empty=lambda symbol, interval, start, end: False
    )
    sys.modules[empty_query_module.__name__] = empty_query_module

    config_module = types.ModuleType("galaxy_db_sync.shared_kernel.utils.config_loader")
    config_module.get_config = lambda *args, **kwargs: None
    sys.modules[config_module.__name__] = config_module

    def merge_db_and_api_data(
        db_data: dict[str, pd.DataFrame],
        api_data: dict[str, pd.DataFrame],
    ) -> dict[str, pd.DataFrame]:
        merged: dict[str, pd.DataFrame] = {}
        for symbol in db_data.keys() | api_data.keys():
            frames = [df for df in [db_data.get(symbol), api_data.get(symbol)] if df is not None]
            if not frames:
                continue
            combined = pd.concat(frames)
            combined = combined[~combined.index.duplicated(keep="last")]
            combined.sort_index(inplace=True)
            merged[symbol] = combined
        return merged

    kline_module = types.ModuleType("galaxy_db_sync.database.services.kline")
    kline_module.kline_service = types.SimpleNamespace(
        query_kline_from_db=lambda symbols, start_date, end_date, interval: {
            symbol: state.db_data[symbol].copy() for symbol in symbols
        },
        merge_db_and_api_data=merge_db_and_api_data,
    )
    sys.modules[kline_module.__name__] = kline_module

    exceptions_module = types.ModuleType("galaxy_db_sync.shared_kernel.exceptions")

    class SDKError(Exception):
        def __init__(self, message: str):
            super().__init__(message)
            self.message = message

    exceptions_module.SDKError = SDKError
    sys.modules[exceptions_module.__name__] = exceptions_module


def _prepare_workload(config: BenchmarkConfig) -> tuple[list[str], StubState]:
    symbols = [f"{600000 + idx:06d}.SH" for idx in range(config.symbols)]
    state = StubState(missing_ranges_by_symbol={}, db_data={})
    base_date = date(2024, 1, 2)

    for symbol_index, symbol in enumerate(symbols):
        state.db_data[symbol] = pd.DataFrame(
            {"close": [float(symbol_index)]},
            index=pd.to_datetime([base_date - timedelta(days=1)]),
        )
        symbol_ranges: list[tuple[date, date]] = []
        for range_index in range(config.ranges_per_symbol):
            start = base_date + timedelta(days=(symbol_index * config.ranges_per_symbol + range_index) * 3)
            end = start + timedelta(days=config.rows_per_range - 1)
            symbol_ranges.append((start, end))
        state.missing_ranges_by_symbol[symbol] = symbol_ranges

    return symbols, state


def _make_frame(symbol: str, begin_date: int, rows_per_range: int) -> pd.DataFrame:
    base = datetime.strptime(str(begin_date), "%Y%m%d")
    index = pd.date_range(base, periods=rows_per_range, freq="D")
    values = [float(int(symbol[:6])) + idx / 100 for idx in range(rows_per_range)]
    return pd.DataFrame({"close": values}, index=index)


def _build_range_groups(
    state: StubState,
    interval_value: int = 10008,
) -> dict[tuple[int, int, int], list[str]]:
    range_groups: dict[tuple[int, int, int], list[str]] = {}
    for symbol, missing_ranges in state.missing_ranges_by_symbol.items():
        for range_start, range_end in missing_ranges:
            key = (
                int(range_start.strftime("%Y%m%d")),
                int(range_end.strftime("%Y%m%d")),
                interval_value,
            )
            range_groups.setdefault(key, []).append(symbol)
    return range_groups


def _load_sync_orchestrator(target_root: Path, namespace: str) -> types.ModuleType:
    kline_dir = target_root / "src" / "galaxy_db_sync" / "application" / "kline"
    package_name = f"{namespace}.kline"
    package_module = types.ModuleType(package_name)
    package_module.__path__ = [str(kline_dir)]
    sys.modules[package_name] = package_module

    for sibling in ["error", "result", "parser"]:
        sibling_path = kline_dir / f"{sibling}.py"
        if sibling_path.exists():
            _load_module(f"{package_name}.{sibling}", sibling_path)

    sync_path = kline_dir / "sync_orchestrator.py"
    if not sync_path.exists():
        raise RuntimeError(f"sync_orchestrator.py not found in {target_root}")
    return _load_module(f"{package_name}.sync_orchestrator", sync_path)


def _detect_implementation(module: types.ModuleType) -> str:
    if hasattr(module, "query_kline_with_results_async"):
        return "async"
    return "threadpool"


def _checksum(
    result: dict[str, pd.DataFrame],
    failed_codes: list[str] | None = None,
) -> dict[str, Any]:
    row_count = sum(len(df) for df in result.values())
    close_sum = round(
        sum(float(df["close"].sum()) for df in result.values() if "close" in df),
        4,
    )
    checksum = {
        "symbols_returned": len(result),
        "row_count": row_count,
        "close_sum": close_sum,
    }
    if failed_codes is not None:
        checksum["failed_count"] = len(failed_codes)
    return checksum


def benchmark_target(target_root: Path, config: BenchmarkConfig) -> dict[str, Any]:
    symbols, state = _prepare_workload(config)
    range_groups = _build_range_groups(state)
    _install_vendor_stubs()
    _install_dependency_stubs(state, config)
    module = _load_sync_orchestrator(target_root, namespace=f"bench_{int(time.time() * 1000)}")
    implementation = _detect_implementation(module)

    results: list[dict[str, Any]] = []
    for max_concurrent in config.max_concurrent_values:
        durations_ms: list[float] = []
        checksum: dict[str, Any] | None = None

        if config.mode == "execute":
            for _ in range(config.warmup):
                module.execute_kline_query(
                    symbol_list=symbols,
                    interval="day",
                    start_date="20240101",
                    end_date="20241231",
                    interval_value=10008,
                    max_concurrent=max_concurrent,
                )

            for _ in range(config.repeats):
                started = time.perf_counter()
                result = module.execute_kline_query(
                    symbol_list=symbols,
                    interval="day",
                    start_date="20240101",
                    end_date="20241231",
                    interval_value=10008,
                    max_concurrent=max_concurrent,
                )
                durations_ms.append((time.perf_counter() - started) * 1000)
                checksum = _checksum(result)
        elif config.mode == "batch":
            for _ in range(config.warmup):
                module.batch_fetch_kline_data(
                    range_groups=range_groups,
                    max_workers=max_concurrent,
                )

            for _ in range(config.repeats):
                started = time.perf_counter()
                result, failed_codes = module.batch_fetch_kline_data(
                    range_groups=range_groups,
                    max_workers=max_concurrent,
                )
                durations_ms.append((time.perf_counter() - started) * 1000)
                checksum = _checksum(result, failed_codes)
        elif config.mode == "batch-async":
            if not hasattr(module, "batch_fetch_kline_data_async"):
                raise RuntimeError(
                    f"batch_fetch_kline_data_async is not available in {target_root}"
                )

            async def run_batch_async_trials() -> dict[str, Any]:
                batch_func = module.batch_fetch_kline_data_async
                for _ in range(config.warmup):
                    await batch_func(
                        range_groups=range_groups,
                        max_concurrent=max_concurrent,
                    )

                async_durations_ms: list[float] = []
                async_checksum: dict[str, Any] | None = None
                for _ in range(config.repeats):
                    started = time.perf_counter()
                    result, failed_codes = await batch_func(
                        range_groups=range_groups,
                        max_concurrent=max_concurrent,
                    )
                    async_durations_ms.append((time.perf_counter() - started) * 1000)
                    async_checksum = _checksum(result, failed_codes)

                if async_checksum is None:
                    raise RuntimeError("Async batch benchmark did not produce a checksum")

                return {
                    "durations_ms": async_durations_ms,
                    "checksum": async_checksum,
                }

            async_report = asyncio.run(run_batch_async_trials())
            durations_ms = async_report["durations_ms"]
            checksum = async_report["checksum"]
        else:
            raise RuntimeError(f"Unsupported benchmark mode: {config.mode}")

        if checksum is None:
            raise RuntimeError("Benchmark did not produce a checksum")

        results.append(
            {
                "max_concurrent": max_concurrent,
                "avg_ms": round(mean(durations_ms), 3),
                "min_ms": round(min(durations_ms), 3),
                "max_ms": round(max(durations_ms), 3),
                "runs_ms": [round(duration, 3) for duration in durations_ms],
                "checksum": checksum,
            }
        )

    return {
        "target_root": str(target_root),
        "implementation": implementation,
        "mode": config.mode,
        "symbols": config.symbols,
        "ranges_per_symbol": config.ranges_per_symbol,
        "rows_per_range": config.rows_per_range,
        "sleep_ms": config.sleep_ms,
        "repeats": config.repeats,
        "results": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-root", required=True, help="Repo root to benchmark")
    parser.add_argument("--symbols", type=int, default=24)
    parser.add_argument("--ranges-per-symbol", type=int, default=3)
    parser.add_argument("--rows-per-range", type=int, default=3)
    parser.add_argument("--sleep-ms", type=float, default=20.0)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument(
        "--max-concurrent",
        type=int,
        action="append",
        dest="max_concurrent_values",
        help="Repeatable max_concurrent value. Defaults to 1 and 5.",
    )
    parser.add_argument(
        "--mode",
        choices=["execute", "batch", "batch-async"],
        default="execute",
        help="Benchmark full execute path, sync batch wrapper, or direct async batch path.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = BenchmarkConfig(
        symbols=args.symbols,
        ranges_per_symbol=args.ranges_per_symbol,
        rows_per_range=args.rows_per_range,
        sleep_ms=args.sleep_ms,
        repeats=args.repeats,
        warmup=args.warmup,
        max_concurrent_values=args.max_concurrent_values or [1, 5],
        mode=args.mode,
    )
    report = benchmark_target(Path(args.target_root).resolve(), config)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Implementation: {report['implementation']}")
        print(f"Mode: {report['mode']}")
        print(f"Target root: {report['target_root']}")
        for result in report["results"]:
            failed_fragment = ""
            if "failed_count" in result["checksum"]:
                failed_fragment = f" failed={result['checksum']['failed_count']}"
            print(
                f"max_concurrent={result['max_concurrent']} "
                f"avg={result['avg_ms']:.3f}ms "
                f"min={result['min_ms']:.3f}ms "
                f"max={result['max_ms']:.3f}ms "
                f"rows={result['checksum']['row_count']}"
                f"{failed_fragment}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
