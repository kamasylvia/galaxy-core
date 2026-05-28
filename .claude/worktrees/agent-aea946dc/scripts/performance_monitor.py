"""K线同步性能监控器.

用于监控批量查询和异步查询的性能指标，包括:
- API调用次数和响应时间
- 批量查询的分组情况
- 并发执行情况
- 数据同步吞吐量
"""

import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class APICallMetrics:
    """API调用指标."""
    call_count: int = 0
    total_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    errors: int = 0
    symbols_per_call: list[int] = field(default_factory=list)

    def add_call(self, duration: float, symbol_count: int = 1, error: bool = False):
        self.call_count += 1
        self.total_duration += duration
        self.min_duration = min(self.min_duration, duration)
        self.max_duration = max(self.max_duration, duration)
        self.symbols_per_call.append(symbol_count)
        if error:
            self.errors += 1

    @property
    def avg_duration(self) -> float:
        return self.total_duration / self.call_count if self.call_count > 0 else 0.0

    @property
    def avg_symbols_per_call(self) -> float:
        return sum(self.symbols_per_call) / len(self.symbols_per_call) if self.symbols_per_call else 0.0

    def __str__(self) -> str:
        return (
            f"API调用次数: {self.call_count}, "
            f"总耗时: {self.total_duration:.2f}s, "
            f"平均耗时: {self.avg_duration:.2f}s, "
            f"最小耗时: {self.min_duration:.2f}s, "
            f"最大耗时: {self.max_duration:.2f}s, "
            f"错误数: {self.errors}, "
            f"平均每批symbol数: {self.avg_symbols_per_call:.1f}"
        )


@dataclass
class BatchMetrics:
    """批量查询指标."""
    total_symbols: int = 0
    unique_ranges: int = 0
    range_groups: dict[tuple, int] = field(default_factory=dict)
    batch_sizes: list[int] = field(default_factory=list)

    def add_group(self, range_key: tuple, symbol_count: int):
        self.range_groups[range_key] = symbol_count
        self.batch_sizes.append(symbol_count)
        self.unique_ranges = len(self.range_groups)

    @property
    def avg_batch_size(self) -> float:
        return sum(self.batch_sizes) / len(self.batch_sizes) if self.batch_sizes else 0.0

    @property
    def max_batch_size(self) -> int:
        return max(self.batch_sizes) if self.batch_sizes else 0

    @property
    def min_batch_size(self) -> int:
        return min(self.batch_sizes) if self.batch_sizes else 0

    def __str__(self) -> str:
        return (
            f"总symbol数: {self.total_symbols}, "
            f"唯一区间数: {self.unique_ranges}, "
            f"平均批次大小: {self.avg_batch_size:.1f}, "
            f"最大批次: {self.max_batch_size}, "
            f"最小批次: {self.min_batch_size}"
        )


@dataclass
class ConcurrencyMetrics:
    """并发执行指标."""
    max_workers: int = 5
    active_threads: int = 0
    peak_concurrent: int = 0
    completed_batches: int = 0
    batch_durations: list[float] = field(default_factory=list)

    def start_batch(self):
        self.active_threads += 1
        self.peak_concurrent = max(self.peak_concurrent, self.active_threads)

    def end_batch(self, duration: float):
        self.active_threads -= 1
        self.completed_batches += 1
        self.batch_durations.append(duration)

    @property
    def avg_batch_duration(self) -> float:
        return sum(self.batch_durations) / len(self.batch_durations) if self.batch_durations else 0.0

    def __str__(self) -> str:
        return (
            f"最大工作线程: {self.max_workers}, "
            f"峰值并发: {self.peak_concurrent}, "
            f"完成批次: {self.completed_batches}, "
            f"平均批次耗时: {self.avg_batch_duration:.2f}s"
        )


@dataclass
class SyncMetrics:
    """同步整体指标."""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_symbols: int = 0
    success_symbols: int = 0
    failed_symbols: int = 0
    total_records: int = 0
    api_metrics: APICallMetrics = field(default_factory=APICallMetrics)
    batch_metrics: BatchMetrics = field(default_factory=BatchMetrics)
    concurrency_metrics: ConcurrencyMetrics = field(default_factory=ConcurrencyMetrics)

    def start(self):
        self.start_time = datetime.now()

    def end(self):
        self.end_time = datetime.now()

    @property
    def total_duration(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def throughput_symbols_per_sec(self) -> float:
        return self.total_symbols / self.total_duration if self.total_duration > 0 else 0.0

    @property
    def throughput_records_per_sec(self) -> float:
        return self.total_records / self.total_duration if self.total_duration > 0 else 0.0

    def generate_report(self) -> str:
        lines = [
            "=" * 60,
            "K线同步性能监控报告",
            "=" * 60,
            f"开始时间: {self.start_time}",
            f"结束时间: {self.end_time}",
            f"总耗时: {self.total_duration:.2f}s",
            "",
            "【总体统计】",
            f"  总symbol数: {self.total_symbols}",
            f"  成功: {self.success_symbols}",
            f"  失败: {self.failed_symbols}",
            f"  总记录数: {self.total_records}",
            f"  Symbol吞吐量: {self.throughput_symbols_per_sec:.2f} symbols/s",
            f"  记录吞吐量: {self.throughput_records_per_sec:.2f} records/s",
            "",
            "【批量查询统计】",
            f"  {self.batch_metrics}",
            "",
            "【API调用统计】",
            f"  {self.api_metrics}",
            "",
            "【并发执行统计】",
            f"  {self.concurrency_metrics}",
            "",
            "【批次详情】",
        ]
        for range_key, count in sorted(self.batch_metrics.range_groups.items()):
            lines.append(f"  区间 {range_key[0]}-{range_key[1]}: {count} symbols")

        lines.append("=" * 60)
        return "\n".join(lines)


class KlinePerformanceMonitor:
    """K线同步性能监控器."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.current_metrics: Optional[SyncMetrics] = None
        self._original_query_kline = None
        self._is_patched = False

    def start_monitoring(self, max_workers: int = 5) -> SyncMetrics:
        """开始监控新的同步会话."""
        self.current_metrics = SyncMetrics()
        self.current_metrics.concurrency_metrics.max_workers = max_workers
        self.current_metrics.start()
        return self.current_metrics

    def end_monitoring(self) -> SyncMetrics:
        """结束监控并返回指标."""
        if self.current_metrics:
            self.current_metrics.end()
            return self.current_metrics
        return SyncMetrics()

    def record_batch_group(self, range_key: tuple, symbol_count: int):
        """记录批量分组信息."""
        if self.current_metrics:
            self.current_metrics.batch_metrics.add_group(range_key, symbol_count)
            self.current_metrics.batch_metrics.total_symbols += symbol_count

    @contextmanager
    def monitor_api_call(self, symbol_count: int = 1):
        """上下文管理器用于监控单个API调用."""
        start = time.perf_counter()
        error = False
        try:
            yield self
        except Exception:
            error = True
            raise
        finally:
            if self.current_metrics:
                duration = time.perf_counter() - start
                self.current_metrics.api_metrics.add_call(duration, symbol_count, error)

    @contextmanager
    def monitor_batch_execution(self):
        """上下文管理器用于监控批次执行."""
        start = time.perf_counter()
        if self.current_metrics:
            self.current_metrics.concurrency_metrics.start_batch()
        try:
            yield self
        finally:
            if self.current_metrics:
                duration = time.perf_counter() - start
                self.current_metrics.concurrency_metrics.end_batch(duration)

    def record_sync_result(self, success: int, failed: int, records: int):
        """记录同步结果."""
        if self.current_metrics:
            self.current_metrics.success_symbols += success
            self.current_metrics.failed_symbols += failed
            self.current_metrics.total_records += records
            self.current_metrics.total_symbols = success + failed

    def patch_amazing_data_client(self, client_class):
        """Patch AmazingDataClient以监控API调用."""
        if self._is_patched:
            return

        self._original_query_kline = client_class.query_kline

        def patched_query_kline(instance, code_list, begin_date, end_date, interval, **kwargs):
            symbol_count = len(code_list)
            with self.monitor_api_call(symbol_count):
                return self._original_query_kline(
                    instance, code_list, begin_date, end_date, interval, **kwargs
                )

        client_class.query_kline = patched_query_kline
        self._is_patched = True
        logger.info("AmazingDataClient 已注入性能监控")

    def unpatch_amazing_data_client(self, client_class):
        """恢复原始的AmazingDataClient."""
        if not self._is_patched or self._original_query_kline is None:
            return

        client_class.query_kline = self._original_query_kline
        self._is_patched = False
        logger.info("AmazingDataClient 性能监控已移除")


# 全局监控器实例
performance_monitor = KlinePerformanceMonitor()
