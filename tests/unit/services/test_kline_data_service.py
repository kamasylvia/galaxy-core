"""KlineDataService 单元测试 — last_sync_date 纯追加模式."""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from galaxy_core.domain.value_objects import Interval, KlineBar
from galaxy_core.services.kline_data_service import KlineDataService, SyncResult


def _make_bar(symbol: str, trade_time: datetime) -> MagicMock:
    """创建模拟 KlineBar 对象."""
    bar = MagicMock(spec=KlineBar)
    bar.symbol = symbol
    bar.trade_time = trade_time
    return bar


def _make_service() -> tuple[KlineDataService, AsyncMock, AsyncMock, MagicMock, MagicMock]:
    """创建 KlineDataService 实例及 mock 端口.

    Returns:
        (service, provider, store, reference, calendar)
        calendar mock 默认 get_trading_days 返空(节假日语义,避免触发空响应检测)。
    """
    provider = AsyncMock()
    store = AsyncMock()
    reference = MagicMock()
    calendar = MagicMock()
    calendar.get_trading_days = AsyncMock(return_value=[])
    service = KlineDataService(provider, store, reference, calendar)
    return service, provider, store, reference, calendar


class TestKlineDataServiceConstruction:
    """验证构造函数签名和端口依赖."""

    def test_constructor_accepts_four_ports(self):
        """KlineDataService 构造函数接收四个端口参数(含 calendar_store)."""
        provider = AsyncMock()
        store = AsyncMock()
        reference = MagicMock()
        calendar = MagicMock()

        service = KlineDataService(
            kline_provider=provider,
            kline_store=store,
            reference_provider=reference,
            calendar_store=calendar,
        )

        assert service._provider is provider
        assert service._store is store
        assert service._reference is reference
        assert service._calendar_store is calendar

    def test_service_has_sync_method(self):
        """KlineDataService 应有 sync 方法."""
        service = KlineDataService(
            kline_provider=AsyncMock(),
            kline_store=AsyncMock(),
            reference_provider=MagicMock(),
            calendar_store=MagicMock(),
        )

        assert hasattr(service, "sync")
        assert callable(service.sync)


class TestKlineDataServiceSync:
    """验证 sync 方法行为 — last_sync_date 纯追加模式."""

    @pytest.mark.asyncio
    async def test_sync_new_symbol_uses_start_minus_one(self):
        """新 symbol（无 last_sync_date 记录）应从 start-1 开始查询 (D-03)."""
        service, provider, store, _, _ = _make_service()

        # 无 last_sync_date 记录
        store.get_last_sync_dates.return_value = {}

        bar = _make_bar("600000.SH", datetime(2024, 1, 15))
        provider.get_kline.return_value = [bar]

        result = await service.sync(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # provider 应以 start-1 = 20231231 开始查询
        provider.get_kline.assert_called_once_with(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240101",  # start_dt - 1 day = 20231231 + 1 = 20240101
            end="20240131",
        )
        # set_last_sync_dates 应被调用，max trade_date = 2024-01-15
        store.set_last_sync_dates.assert_called_once_with(
            {"600000.SH": date(2024, 1, 15)},
            Interval.DAY,
        )
        assert result.success_count == 1
        assert result.synced_records == 1

    @pytest.mark.asyncio
    async def test_sync_existing_symbol_uses_last_sync_date_plus_one(self):
        """已有 symbol 应从 last_sync_date+1 开始查询."""
        service, provider, store, _, _ = _make_service()

        # last_sync_date = 2024-01-10
        store.get_last_sync_dates.return_value = {
            "600000.SH": date(2024, 1, 10),
        }

        bar = _make_bar("600000.SH", datetime(2024, 1, 15))
        provider.get_kline.return_value = [bar]

        result = await service.sync(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # query_start = last_sync_date + 1 = 20240111
        provider.get_kline.assert_called_once_with(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240111",
            end="20240131",
        )
        assert result.success_count == 1

    @pytest.mark.asyncio
    async def test_sync_empty_api_response_does_not_advance_last_sync_date(self):
        """API 返回空数据时，last_sync_date 不推进 (D-02)."""
        service, provider, store, _, _ = _make_service()

        store.get_last_sync_dates.return_value = {
            "600000.SH": date(2024, 1, 10),
        }
        provider.get_kline.return_value = []  # API 返回空

        result = await service.sync(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # set_last_sync_dates 不应被调用
        store.set_last_sync_dates.assert_not_called()
        assert result.synced_records == 0
        assert result.success_count == 1

    @pytest.mark.asyncio
    async def test_sync_updates_last_sync_date_to_max_trade_date(self):
        """同步后 last_sync_date 应更新为实际 MAX(trade_time)."""
        service, provider, store, _, _ = _make_service()

        store.get_last_sync_dates.return_value = {}

        bars = [
            _make_bar("600000.SH", datetime(2024, 1, 5)),
            _make_bar("600000.SH", datetime(2024, 1, 10)),
            _make_bar("600000.SH", datetime(2024, 1, 3)),  # 非时间顺序
        ]
        provider.get_kline.return_value = bars

        result = await service.sync(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # last_sync_date 应为 max(trade_time) = 2024-01-10
        store.set_last_sync_dates.assert_called_once_with(
            {"600000.SH": date(2024, 1, 10)},
            Interval.DAY,
        )
        assert result.synced_records == 3

    @pytest.mark.asyncio
    async def test_sync_skips_when_start_greater_than_end(self):
        """last_sync_date >= end 时，应跳过查询 (query_start > query_end)."""
        service, provider, store, _, _ = _make_service()

        # last_sync_date = end date -> query_start = end+1 > end
        store.get_last_sync_dates.return_value = {
            "600000.SH": date(2024, 1, 31),
        }

        result = await service.sync(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # provider 不应被调用
        provider.get_kline.assert_not_called()
        # 所有 symbol 视为成功（已最新）
        assert result.success_count == 1
        assert result.synced_records == 0

    @pytest.mark.asyncio
    async def test_sync_groups_symbols_by_same_query_range(self):
        """不同 last_sync_date 的 symbols 应分组为不同的 API 调用."""
        service, provider, store, _, _ = _make_service()

        store.get_last_sync_dates.return_value = {
            "600000.SH": date(2024, 1, 10),
            "600001.SH": date(2024, 1, 15),
        }

        # 每次 API 调用返回对应 symbol 的数据
        call_count = 0

        async def mock_get_kline(symbols, interval, start, end):
            nonlocal call_count
            call_count += 1
            bars = []
            for s in symbols:
                bars.append(_make_bar(s, datetime(2024, 1, 20)))
            return bars

        provider.get_kline.side_effect = mock_get_kline

        result = await service.sync(
            symbols=["600000.SH", "600001.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # 两个不同的 last_sync_date，应产生两个不同查询范围
        assert provider.get_kline.call_count == 2
        assert result.success_count == 2

    @pytest.mark.asyncio
    async def test_sync_fetches_missing_data(self):
        """基本快乐路径：已有 last_sync_date，API 返回数据."""
        service, provider, store, _, _ = _make_service()

        store.get_last_sync_dates.return_value = {
            "600000.SH": date(2024, 1, 5),
        }

        bars = [_make_bar("600000.SH", datetime(2024, 1, 8))]
        provider.get_kline.return_value = bars

        result = await service.sync(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # query_start = last+1 = 20240106
        provider.get_kline.assert_called_once_with(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240106",
            end="20240131",
        )
        store.save_kline.assert_called_once_with(bars, Interval.DAY)
        store.set_last_sync_dates.assert_called_once_with(
            {"600000.SH": date(2024, 1, 8)},
            Interval.DAY,
        )
        assert result.synced_records == 1
        assert result.success_count == 1

    @pytest.mark.asyncio
    async def test_sync_api_error_marks_failed(self):
        """API 异常时，symbol 应标记为 failed，继续同步其他 symbols."""
        service, provider, store, _, _ = _make_service()

        # 不同 last_sync_date 确保分到不同组，各自独立调用 API
        store.get_last_sync_dates.return_value = {
            "600000.SH": date(2024, 1, 10),
            "600001.SH": date(2024, 1, 15),
        }

        async def mock_get_kline(symbols, interval, start, end):
            if "600000.SH" in symbols:
                raise Exception("API error")
            return [_make_bar(s, datetime(2024, 1, 20)) for s in symbols]

        provider.get_kline.side_effect = mock_get_kline

        result = await service.sync(
            symbols=["600000.SH", "600001.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        assert "600000.SH" in result.failed_codes
        assert result.success_count == 1

    @pytest.mark.asyncio
    async def test_sync_all_symbols_already_up_to_date(self):
        """所有 symbols 的 last_sync_date >= end 时，不调用 API."""
        service, provider, store, _, _ = _make_service()

        store.get_last_sync_dates.return_value = {
            "600000.SH": date(2024, 1, 31),
            "600001.SH": date(2024, 2, 1),  # 超过 end
        }

        result = await service.sync(
            symbols=["600000.SH", "600001.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        provider.get_kline.assert_not_called()
        assert result.success_count == 2
        assert result.synced_records == 0
        assert result.failed_codes == []

    @pytest.mark.asyncio
    async def test_sync_multiple_symbols_same_range_single_api_call(self):
        """多个 symbols 共享相同查询范围时，合并为一次 API 调用."""
        service, provider, store, _, _ = _make_service()

        # 两个 symbol 有相同的 last_sync_date
        store.get_last_sync_dates.return_value = {
            "600000.SH": date(2024, 1, 10),
            "600001.SH": date(2024, 1, 10),
        }

        bars = [
            _make_bar("600000.SH", datetime(2024, 1, 15)),
            _make_bar("600001.SH", datetime(2024, 1, 15)),
        ]
        provider.get_kline.return_value = bars

        result = await service.sync(
            symbols=["600000.SH", "600001.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # 相同 range 合并为一次调用
        assert provider.get_kline.call_count == 1
        call_args = provider.get_kline.call_args
        assert set(call_args.kwargs["symbols"]) == {"600000.SH", "600001.SH"}
        assert call_args.kwargs["start"] == "20240111"

        # set_last_sync_dates 应包含两个 symbol
        set_call = store.set_last_sync_dates.call_args
        assert set(set_call.args[0].keys()) == {"600000.SH", "600001.SH"}

        assert result.success_count == 2
        assert result.synced_records == 2

    @pytest.mark.asyncio
    async def test_sync_empty_symbols_list(self):
        """空 symbols 列表应返回空结果."""
        service, provider, store, _, _ = _make_service()

        store.get_last_sync_dates.return_value = {}

        result = await service.sync(
            symbols=[],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        provider.get_kline.assert_not_called()
        assert result.total_symbols == 0
        assert result.success_count == 0

    @pytest.mark.asyncio
    async def test_sync_updates_last_sync_date_per_symbol_independently(self):
        """多 symbol 同步时，各自 last_sync_date 独立更新."""
        service, provider, store, _, _ = _make_service()

        store.get_last_sync_dates.return_value = {}

        bars = [
            _make_bar("600000.SH", datetime(2024, 1, 5)),
            _make_bar("600000.SH", datetime(2024, 1, 10)),
            _make_bar("600001.SH", datetime(2024, 1, 8)),
            _make_bar("600001.SH", datetime(2024, 1, 20)),
        ]
        provider.get_kline.return_value = bars

        result = await service.sync(
            symbols=["600000.SH", "600001.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        set_call = store.set_last_sync_dates.call_args
        symbol_dates = set_call.args[0]
        assert symbol_dates["600000.SH"] == date(2024, 1, 10)
        assert symbol_dates["600001.SH"] == date(2024, 1, 20)

        assert result.synced_records == 4
        assert result.success_count == 2


class TestKlineDataServiceConfigStart:
    """验证配置驱动的默认开始日期."""

    def test_resolve_default_start_reads_from_config(self):
        """Mock get_section('kline') 返回 default_start_date，验证解析结果."""
        service, _, _, _, _ = _make_service()

        with patch(
            "galaxy_core.shared_kernel.utils.config_loader.get_section",
            return_value={"default_start_date": "20200101"},
        ):
            result = service._resolve_default_start(["any"])

        assert result == "20200101"

    def test_resolve_default_start_fallback_when_config_missing(self):
        """Mock get_section('kline') 返回空字典，验证回退到 20130101."""
        service, _, _, _, _ = _make_service()

        with patch(
            "galaxy_core.shared_kernel.utils.config_loader.get_section",
            return_value={},
        ):
            result = service._resolve_default_start(["any"])

        assert result == "20130101"


class TestApiBatching:
    """验证 API 侧分批:组内 symbols 超过 chunk_size 时拆分为多次 API 调用.

    背景:空表首启时所有 symbol 同组,整组传 SDK 会内存爆炸
    (ETF 1585 只→2.9GB,A 股 5200 只必崩)。详见 AGENTS.md。
    chunk_size 由 resolve_kline_chunk_size(interval, window) 按内存预算自适应:
    全量大窗口分批防 OOM,增量小窗口放大 chunk 避免浪费 API 调用。
    """

    @pytest.mark.asyncio
    async def test_large_group_split_into_chunks(self):
        """组内 symbols 数 > chunk_size 时,拆分为多次 API 调用."""
        service, provider, store, _, _ = _make_service()
        # mock 小 chunk_size 让少量 symbol 即可触发分批
        with patch(
            "galaxy_core.services.kline_data_service.resolve_kline_chunk_size",
            return_value=3,
        ):
            store.get_last_sync_dates.return_value = {}  # 全新 → 同一组
            # 8 只 symbol,chunk_size=3 → 3 chunk (3+3+2)
            symbols = [f"60000{i}.SH" for i in range(8)]
            provider.get_kline.return_value = []  # 空响应,聚焦验证调用次数

            await service.sync(
                symbols=symbols,
                interval=Interval.DAY,
                start="20240101",
                end="20240131",
            )

        # 8 只 / chunk_size 3 = ceil(8/3) = 3 次 API 调用
        assert provider.get_kline.call_count == 3
        # 每次调用的 symbols 长度 ≤ chunk_size
        for call in provider.get_kline.call_args_list:
            assert len(call.kwargs["symbols"]) <= 3
        # 三批的 sizes: 3, 3, 2
        sizes = [len(c.kwargs["symbols"]) for c in provider.get_kline.call_args_list]
        assert sizes == [3, 3, 2]

    @pytest.mark.asyncio
    async def test_small_group_not_split(self):
        """组内 symbols 数 ≤ chunk_size 时,保持单次 API 调用(不拆分).

        30 天窗口 day:chunk = 158万/30 ≈ 52666,2 只 symbol << chunk → 1 次调用。
        """
        service, provider, store, _, _ = _make_service()

        store.get_last_sync_dates.return_value = {}
        symbols = ["600000.SH", "600001.SH"]
        provider.get_kline.return_value = [
            _make_bar("600000.SH", datetime(2024, 1, 15)),
            _make_bar("600001.SH", datetime(2024, 1, 15)),
        ]

        await service.sync(
            symbols=symbols,
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # 不拆分,单次调用
        assert provider.get_kline.call_count == 1
        assert set(provider.get_kline.call_args.kwargs["symbols"]) == {
            "600000.SH",
            "600001.SH",
        }

    @pytest.mark.asyncio
    async def test_chunk_size_boundary_single_chunk(self):
        """symbols 数 == chunk_size 时,正好单次调用(边界)."""
        service, provider, store, _, _ = _make_service()
        with patch(
            "galaxy_core.services.kline_data_service.resolve_kline_chunk_size",
            return_value=5,
        ):
            store.get_last_sync_dates.return_value = {}
            symbols = [f"60000{i}.SH" for i in range(5)]  # 恰好 == chunk_size
            provider.get_kline.return_value = []

            await service.sync(
                symbols=symbols,
                interval=Interval.DAY,
                start="20240101",
                end="20240131",
            )

        # 5/5 = 1 次,不拆分
        assert provider.get_kline.call_count == 1
        assert len(provider.get_kline.call_args.kwargs["symbols"]) == 5

    @pytest.mark.asyncio
    async def test_single_chunk_failure_does_not_block_others(self):
        """某 chunk 失败 → 进 failed_codes,后续 chunk 仍执行(不阻断)."""
        service, provider, store, _, _ = _make_service()
        with patch(
            "galaxy_core.services.kline_data_service.resolve_kline_chunk_size",
            return_value=2,
        ):
            store.get_last_sync_dates.return_value = {}
            symbols = ["600000.SH", "600001.SH", "600002.SH", "600003.SH"]
            # 4 只 / chunk_size 2 = 2 chunk。第 1 chunk 抛异常,第 2 chunk 正常
            provider.get_kline.side_effect = [
                Exception("API timeout"),
                [_make_bar("600002.SH", datetime(2024, 1, 15))],
            ]

            result = await service.sync(
                symbols=symbols,
                interval=Interval.DAY,
                start="20240101",
                end="20240131",
            )

        # 两次调用都发生(第 1 次失败不阻断第 2 次)
        assert provider.get_kline.call_count == 2
        # 失败 chunk 的 2 只进 failed_codes
        assert set(result.failed_codes) == {"600000.SH", "600001.SH"}
        # 成功 chunk 的 symbol 进 last_sync_date
        set_call = store.set_last_sync_dates.call_args
        assert "600002.SH" in set_call.args[0]

    @pytest.mark.asyncio
    async def test_full_window_week_fewer_batches_than_day(self):
        """全量窗口(13年):day 分批 > week 分批.

        内存预算 + kline_code_cap=500(2026-08-06):
        day(4934行/只):158万/4934=320(预算主导,<cap 500)→ 2400/320 ≈ 8 批
        week(986行/只):158万/986=1602,被 cap 拦到 500 → 2400/500 ≈ 5 批
        """
        service, provider, store, _, _ = _make_service()
        store.get_last_sync_dates.return_value = {}
        symbols = [f"{600000 + i:06d}.SH" for i in range(2400)]
        provider.get_kline.return_value = []

        # 全量 day:chunk=320,2400/320 ≈ 8 批
        await service.sync(
            symbols=symbols,
            interval=Interval.DAY,
            start="20130101",
            end="20260708",
        )
        day_calls = provider.get_kline.call_count
        assert day_calls >= 7  # ~8 批

        # 全量 week:chunk=500(cap),2400/500 = 5 批
        provider.get_kline.reset_mock()
        await service.sync(
            symbols=symbols,
            interval=Interval.WEEK,
            start="20130101",
            end="20260708",
        )
        week_calls = provider.get_kline.call_count
        assert week_calls == 5  # ceil(2400/500)
        # week 批数 < day(week 每 symbol 行数少 → chunk 仍更大)
        assert week_calls < day_calls

    @pytest.mark.asyncio
    async def test_incremental_window_splits_by_cap(self):
        """增量窗口(1天):chunk 被 kline_code_cap 拦到 500/批(2026-08-06).

        SDK 对 3000+ 只 code_list 的 day 增量不稳定(混合市场静默丢沪深 /
        单市场大组卡死),增量不再单次调用,改 500/批分批。
        """
        service, provider, store, _, _ = _make_service()
        # 所有 symbol 已有 last_sync_date(增量场景)
        from datetime import date as d

        store.get_last_sync_dates.return_value = {
            f"{600000 + i:06d}.SH": d(2026, 7, 7) for i in range(5529)
        }
        provider.get_kline.return_value = []

        await service.sync(
            symbols=[f"{600000 + i:06d}.SH" for i in range(5529)],
            interval=Interval.DAY,
            start="20240101",
            end="20260708",
        )

        # 增量窗口 = 20260708~20260708(1 天,rows_per_symbol=1)
        # chunk=min(158万, 500)=500 → 5529/500 = 12 批(cap 生效)
        assert provider.get_kline.call_count == 12  # ceil(5529/500)
