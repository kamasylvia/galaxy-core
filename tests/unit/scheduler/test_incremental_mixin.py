"""IncrementalSyncMixin 单元测试(Phase 03 03-03).

测试 _resolve_incremental_range + _max_date_from_records。
mock self._last_sync_store(LastSyncDateStore)+ 构造 mixin 子类。
"""

import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from galaxy_core.application.scheduler.jobs._incremental_mixin import (
    IncrementalSyncMixin,
)
from galaxy_core.shared_kernel.utils.constants import DEFAULT_FIRST_SYNC_DATE


class _MixinImpl(IncrementalSyncMixin):
    """测试用 mixin 子类,注入 mock _last_sync_store."""

    def __init__(self, last_sync_store):
        self._last_sync_store = last_sync_store


def _make_store(get_return=None):
    store = MagicMock()
    store.get_last_sync_date = AsyncMock(return_value=get_return)
    return store


class TestResolveIncrementalRange:
    async def test_empty_table_returns_first_sync_date(self):
        """last=None(空表首次)→ begin=DEFAULT_FIRST_SYNC_DATE=20130101."""
        impl = _MixinImpl(_make_store(get_return=None))
        begin, end = await impl._resolve_incremental_range(
            "index_weight", "000300.SH", date(2024, 1, 15)
        )
        assert begin == DEFAULT_FIRST_SYNC_DATE == 20130101
        assert end == 20240115

    async def test_existing_data_returns_last_plus_one(self):
        """last=2024-01-10 → begin=20240111(last+1)."""
        store = _make_store(get_return=date(2024, 1, 10))
        impl = _MixinImpl(store)
        begin, end = await impl._resolve_incremental_range(
            "index_weight", "000300.SH", date(2024, 1, 15)
        )
        assert begin == 20240111
        assert end == 20240115

    async def test_custom_first_sync_date(self):
        """覆盖默认 first_sync_date(如某表从 20080101 起)."""
        impl = _MixinImpl(_make_store(get_return=None))
        begin, _ = await impl._resolve_incremental_range(
            "industry_weight", "801010", date(2024, 1, 15), first_sync_date=20080101
        )
        assert begin == 20080101

    async def test_scope_key_none_global(self):
        """scope_key=None(全市场汇总 margin_summary)透传给 store."""
        store = _make_store(get_return=date(2024, 1, 10))
        impl = _MixinImpl(store)
        await impl._resolve_incremental_range(
            "margin_summary", None, date(2024, 1, 15)
        )
        store.get_last_sync_date.assert_called_once_with("margin_summary", None)

    async def test_scope_key_passed_through(self):
        """scope_key 非空时透传(market_code/index_code)."""
        store = _make_store(get_return=None)
        impl = _MixinImpl(store)
        await impl._resolve_incremental_range(
            "long_hu_bang", "600000.SH", date(2024, 1, 15)
        )
        store.get_last_sync_date.assert_called_once_with("long_hu_bang", "600000.SH")

    async def test_end_always_today(self):
        """end 永远 = today(YYYYMMDD)."""
        impl = _MixinImpl(_make_store(get_return=None))
        for today in [date(2024, 1, 1), date(2025, 12, 31), date(2026, 6, 19)]:
            _, end = await impl._resolve_incremental_range(
                "x", None, today
            )
            assert end == int(today.strftime("%Y%m%d"))

    async def test_last_plus_one_handles_month_boundary(self):
        """last=2024-01-31 → begin=20240201(跨月)."""
        store = _make_store(get_return=date(2024, 1, 31))
        impl = _MixinImpl(store)
        begin, _ = await impl._resolve_incremental_range(
            "x", None, date(2024, 2, 5)
        )
        assert begin == 20240201


class TestMaxDateFromRecords:
    """_max_date_from_records 静态方法."""

    def test_empty_returns_none(self):
        assert IncrementalSyncMixin._max_date_from_records([]) is None

    def test_returns_max(self):
        records = [
            SimpleNamespace(trade_date=date(2024, 1, 10)),
            SimpleNamespace(trade_date=date(2024, 1, 15)),
            SimpleNamespace(trade_date=date(2024, 1, 12)),
        ]
        assert IncrementalSyncMixin._max_date_from_records(records) == date(2024, 1, 15)

    def test_skips_none(self):
        """records 含 None date 跳过."""
        records = [
            SimpleNamespace(trade_date=date(2024, 1, 10)),
            SimpleNamespace(trade_date=None),
            SimpleNamespace(trade_date=date(2024, 1, 20)),
        ]
        assert IncrementalSyncMixin._max_date_from_records(records) == date(2024, 1, 20)

    def test_all_none_returns_none(self):
        records = [SimpleNamespace(trade_date=None), SimpleNamespace(trade_date=None)]
        assert IncrementalSyncMixin._max_date_from_records(records) is None

    def test_custom_date_attr(self):
        """自定义 date_attr(如 margin_summary 用 trade_date, 其他表可能用 date)."""
        records = [SimpleNamespace(date=date(2024, 3, 1))]
        assert IncrementalSyncMixin._max_date_from_records(records, date_attr="date") == date(2024, 3, 1)


class TestDefaultFirstSyncDateConstant:
    def test_constant_is_20130101(self):
        assert DEFAULT_FIRST_SYNC_DATE == 20130101
