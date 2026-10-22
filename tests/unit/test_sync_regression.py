"""SYNC-05 单元回归测试 — KlineDataService.sync() 核心场景.

覆盖日常增量同步、首次全量同步、退市 symbol 过滤、空响应不推进 last_sync_date、
多周期参数化等场景。使用 unittest.mock 的 AsyncMock/MagicMock mock KlineProviderPort
和 KlineStorePort。
"""

import sys
import types
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

# Mock AmazingData SDK before any galaxy_core imports
if "AmazingData" not in sys.modules:
    sys.modules["AmazingData"] = types.SimpleNamespace(
        login=lambda **kwargs: None,
        logout=lambda *args, **kwargs: None,
        BaseData=lambda: types.SimpleNamespace(get_calendar=lambda *args, **kwargs: []),
        InfoData=lambda: types.SimpleNamespace(),
        MarketData=lambda calendar: types.SimpleNamespace(query_kline=lambda **kwargs: {}),
    )

if "akshare" not in sys.modules:
    sys.modules["akshare"] = types.SimpleNamespace()

if "tgw" not in sys.modules:
    sys.modules["tgw"] = types.SimpleNamespace()

# Mock config_loader — 返回默认值而非空 dict，避免污染集成测试
config_loader_mock = types.ModuleType("galaxy_core.shared_kernel.utils.config_loader")

def _mock_get_config(*args, **kwargs):
    if len(args) >= 3:
        return args[2]
    return kwargs.get("default")

config_loader_mock.get_config = _mock_get_config
config_loader_mock.get_section = lambda *args, **kwargs: {}
config_loader_mock.load_config_dict = lambda *args, **kwargs: {}
sys.modules["galaxy_core.shared_kernel.utils.config_loader"] = config_loader_mock

from galaxy_core.domain.value_objects import Interval, KlineBar, SecurityType
from galaxy_core.services.kline_data_service import KlineDataService, SyncResult
from galaxy_core.shared_kernel.exceptions.api import EmptyResponseError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bar(symbol: str, trade_time: datetime, **kwargs) -> KlineBar:
    """创建 KlineBar 实例（填充默认值）."""
    defaults = {
        "open": 10.0,
        "high": 11.0,
        "low": 9.0,
        "close": 10.5,
        "volume": 1000,
        "amount": 10000.0,
        "security_type": SecurityType.EXTRA_ETF,
    }
    defaults.update(kwargs)
    return KlineBar(symbol=symbol, trade_time=trade_time, **defaults)


def _make_service() -> tuple[KlineDataService, MagicMock, MagicMock, MagicMock, MagicMock]:
    """创建 KlineDataService 实例及 mock 依赖.

    Returns:
        (service, mock_provider, mock_store, mock_reference, mock_calendar)
        mock_calendar.get_trading_days 默认返空(节假日语义,避免触发空响应检测)。
    """
    mock_provider = MagicMock()
    mock_store = MagicMock()
    mock_reference = MagicMock()
    mock_calendar = MagicMock()
    mock_calendar.get_trading_days = AsyncMock(return_value=[])
    service = KlineDataService(
        mock_provider, mock_store, mock_reference, mock_calendar
    )
    return service, mock_provider, mock_store, mock_reference, mock_calendar


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSyncRegression:
    """SYNC-05 回归测试 — KlineDataService.sync() 核心场景."""

    async def test_daily_incremental_sync(self):
        """日常增量同步：last_sync_date 存在时从 last+1 开始查询."""
        service, provider, store, _, _ = _make_service()

        store.get_last_sync_dates = AsyncMock(
            return_value={"600000.SH": date(2024, 1, 10)}
        )
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()

        bar = _make_bar("600000.SH", datetime(2024, 1, 15, 10, 0, 0))
        provider.get_kline = AsyncMock(return_value=[bar])

        result = await service.sync(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # 验证 provider.get_kline 被调用，且 start 为 "20240111" (last+1)
        provider.get_kline.assert_called_once()
        call_kwargs = provider.get_kline.call_args.kwargs
        assert call_kwargs["start"] == "20240111"
        assert call_kwargs["end"] == "20240131"
        assert call_kwargs["interval"] == Interval.DAY

        # 验证 set_last_sync_dates 被调用，传入最大 trade_date
        store.set_last_sync_dates.assert_called_once()
        set_args = store.set_last_sync_dates.call_args.args
        assert set_args[0] == {"600000.SH": date(2024, 1, 15)}
        assert set_args[1] == Interval.DAY

        # 验证结果
        assert isinstance(result, SyncResult)
        assert result.success_count == 1
        assert result.synced_records == 1
        assert result.total_symbols == 1
        assert result.failed_codes == []

    async def test_first_time_full_sync(self):
        """首次全量同步：无 last_sync_date 记录时从 start 开始查询 (D-03 已变更)."""
        service, provider, store, _, _ = _make_service()

        store.get_last_sync_dates = AsyncMock(return_value={})
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()

        bars = [
            _make_bar("600000.SH", datetime(2024, 1, 2, 10, 0, 0)),
            _make_bar("600000.SH", datetime(2024, 1, 3, 10, 0, 0)),
            _make_bar("600000.SH", datetime(2024, 1, 4, 10, 0, 0)),
            _make_bar("600000.SH", datetime(2024, 1, 5, 10, 0, 0)),
        ]
        provider.get_kline = AsyncMock(return_value=bars)

        result = await service.sync(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # 验证 provider.get_kline 被调用，且 start 为 "20240101"
        provider.get_kline.assert_called_once()
        call_kwargs = provider.get_kline.call_args.kwargs
        assert call_kwargs["start"] == "20240101"
        assert call_kwargs["end"] == "20240131"

        # 验证 set_last_sync_dates 被调用，传入实际最大 trade_date
        store.set_last_sync_dates.assert_called_once()
        set_args = store.set_last_sync_dates.call_args.args
        assert set_args[0] == {"600000.SH": date(2024, 1, 5)}
        assert set_args[1] == Interval.DAY

        # 验证结果
        assert result.synced_records == 4
        assert result.success_count == 1

    async def test_delisted_symbol_filtering(self):
        """退市 symbol 过滤：空 symbols 列表时 provider.get_kline 不被调用."""
        service, provider, store, _, _ = _make_service()

        store.get_last_sync_dates = AsyncMock(return_value={})
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()
        provider.get_kline = AsyncMock(return_value=[])

        result = await service.sync(
            symbols=[],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # 验证 provider.get_kline 不被调用
        provider.get_kline.assert_not_called()
        store.save_kline.assert_not_called()
        store.set_last_sync_dates.assert_not_called()

        # 验证结果
        assert result.success_count == 0
        assert result.synced_records == 0
        assert result.total_symbols == 0

    async def test_empty_api_response_does_not_advance_last_sync_date(self):
        """空 API 响应不推进 last_sync_date (D-02)."""
        service, provider, store, _, _ = _make_service()

        store.get_last_sync_dates = AsyncMock(
            return_value={"600000.SH": date(2024, 1, 10)}
        )
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()
        provider.get_kline = AsyncMock(return_value=[])

        result = await service.sync(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # 验证 provider.get_kline 被调用（查询范围正确）
        provider.get_kline.assert_called_once()

        # 验证 save_kline 不被调用（空数据）
        store.save_kline.assert_not_called()

        # 验证 set_last_sync_dates 不被调用（空响应不推进）
        store.set_last_sync_dates.assert_not_called()

        # 验证结果
        assert result.success_count == 1  # symbol 本身未失败
        assert result.synced_records == 0

    @pytest.mark.parametrize(
        "interval",
        [
            Interval.DAY,
            Interval.WEEK,
            Interval.MONTH,
            Interval.SEASON,
            Interval.YEAR,
        ],
    )
    async def test_sync_across_intervals(self, interval: Interval):
        """长周期参数化：day/week/month/season/year 均能正确同步."""
        service, provider, store, _, _ = _make_service()

        store.get_last_sync_dates = AsyncMock(return_value={})
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()

        bar = _make_bar("600000.SH", datetime(2024, 1, 15, 10, 0, 0))
        provider.get_kline = AsyncMock(return_value=[bar])

        result = await service.sync(
            symbols=["600000.SH"],
            interval=interval,
            start="20240101",
            end="20240131",
        )

        # 验证 provider.get_kline 被调用，interval 正确
        provider.get_kline.assert_called_once()
        call_kwargs = provider.get_kline.call_args.kwargs
        assert call_kwargs["interval"] == interval

        # 验证 save_kline 被调用
        store.save_kline.assert_called_once()
        save_args = store.save_kline.call_args.args
        assert save_args[1] == interval

        # 验证 set_last_sync_dates 被调用
        store.set_last_sync_dates.assert_called_once()
        set_args = store.set_last_sync_dates.call_args.args
        assert set_args[1] == interval

        # 验证结果
        assert result.success_count == 1
        assert result.synced_records == 1

    async def test_multiple_symbols_batch_sync(self):
        """多 symbol 批量同步：相同查询范围的 symbol 合并为一次 API 调用."""
        service, provider, store, _, _ = _make_service()

        store.get_last_sync_dates = AsyncMock(return_value={})
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()

        bars = [
            _make_bar("600000.SH", datetime(2024, 1, 15, 10, 0, 0)),
            _make_bar("601398.SH", datetime(2024, 1, 15, 10, 0, 0)),
        ]
        provider.get_kline = AsyncMock(return_value=bars)

        result = await service.sync(
            symbols=["600000.SH", "601398.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # 验证 provider.get_kline 只被调用一次（两个 symbol 合并）
        assert provider.get_kline.call_count == 1
        call_kwargs = provider.get_kline.call_args.kwargs
        assert sorted(call_kwargs["symbols"]) == sorted(["600000.SH", "601398.SH"])

        # 验证结果
        assert result.success_count == 2
        assert result.synced_records == 2

    async def test_api_failure_records_failed_codes(self):
        """API 失败时记录失败 symbol，不中断其他批次."""
        service, provider, store, _, _ = _make_service()

        store.get_last_sync_dates = AsyncMock(
            return_value={
                "600000.SH": date(2024, 1, 10),
                "601398.SH": date(2024, 1, 10),
            }
        )
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()

        # 两个 symbol 相同查询范围，但 API 抛异常
        provider.get_kline = AsyncMock(side_effect=Exception("API timeout"))

        result = await service.sync(
            symbols=["600000.SH", "601398.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # 验证 provider.get_kline 被调用一次（合并批次）
        assert provider.get_kline.call_count == 1

        # 验证 set_last_sync_dates 不被调用（无成功数据）
        store.set_last_sync_dates.assert_not_called()

        # 验证失败结果
        assert result.success_count == 0
        assert result.synced_records == 0
        assert len(result.failed_codes) == 2
        assert "600000.SH" in result.failed_codes
        assert "601398.SH" in result.failed_codes

    async def test_all_symbols_up_to_date_no_api_call(self):
        """所有 symbol 数据已最新时不调用 API."""
        service, provider, store, _, _ = _make_service()

        # last_sync_date 已经等于 end_date，无需同步
        store.get_last_sync_dates = AsyncMock(
            return_value={"600000.SH": date(2024, 1, 31)}
        )
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()
        provider.get_kline = AsyncMock(return_value=[])

        result = await service.sync(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )

        # 验证 provider.get_kline 不被调用
        provider.get_kline.assert_not_called()
        store.save_kline.assert_not_called()
        store.set_last_sync_dates.assert_not_called()

        # 验证结果
        assert result.success_count == 1
        assert result.synced_records == 0
        assert result.total_symbols == 1


@pytest.mark.asyncio
class TestEmptyResponseDetection:
    """AM 返空检测(2026-08-11 根治 + 2026-08-14 覆盖率补强).

    场景:凌晨 AM 时段性返空(数据存在但 API 返 0 条或少量历史补数据),
    scheduler 静默 mark_success(0) 导致数据缺口。

    检测逻辑(2026-08-14 覆盖率补强):
    - end 是交易日 + 覆盖率 < 10% → raise(捕获全空 + 部分空)
    - end 非交易日 + total_synced==0 + 窗口含交易日 → raise(长周期/节假日全空)
    - end 非交易日 + total_synced>0 → 不 raise(有数据)
    - symbols_needing_sync==0 → 不检测(无 symbol 需同步)
    """

    async def test_empty_response_with_trading_days_raises(self):
        """全 chunk 返空 + end 是交易日 → raise(覆盖率 0%)."""
        service, provider, store, _, calendar = _make_service()

        store.get_last_sync_dates = AsyncMock(
            return_value={"600000.SH": date(2024, 1, 10)}
        )
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()
        provider.get_kline = AsyncMock(return_value=[])  # API 返空
        # end=20240131 是交易日
        calendar.get_trading_days = AsyncMock(
            return_value=[date(2024, 1, 31)]
        )

        with pytest.raises(EmptyResponseError) as exc_info:
            await service.sync(
                symbols=["600000.SH"],
                interval=Interval.DAY,
                start="20240101",
                end="20240131",
            )
        # 错误消息应含覆盖率 + 目标日期
        msg = str(exc_info.value)
        assert "覆盖率仅 0.0%" in msg
        assert "20240131" in msg
        # 不应推进 last_sync_date(无成功数据)
        store.set_last_sync_dates.assert_not_called()

    async def test_partial_empty_with_historical_data_raises(self):
        """部分空:少量历史补数据(< end_date)混入 → 覆盖率 0% → raise.

        回归 2026-08-13 案例:8056 只需同步,180 条旧股退市前数据(非当日)
        入库,total_synced=180 但当日覆盖率 0%。原 total_synced==0 检测漏过,
        覆盖率检测捕获。
        """
        service, provider, store, _, calendar = _make_service()

        # 2 只 symbol,1 只 last_sync=1/10(需同步),1 只 last_sync=2016(旧)
        store.get_last_sync_dates = AsyncMock(
            return_value={
                "600000.SH": date(2024, 1, 10),
                "600001.SH": date(2016, 6, 13),
            }
        )
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()
        # 600000.SH 当日返空,600001.SH 返历史数据(退市前 2018)
        provider.get_kline = AsyncMock(
            return_value=[_make_bar("600001.SH", datetime(2018, 6, 30))]
        )
        # end=1/31 是交易日
        calendar.get_trading_days = AsyncMock(
            return_value=[date(2024, 1, 31)]
        )

        with pytest.raises(EmptyResponseError) as exc_info:
            await service.sync(
                symbols=["600000.SH", "600001.SH"],
                interval=Interval.DAY,
                start="20130101",
                end="20240131",
            )
        msg = str(exc_info.value)
        # 覆盖率 0%(2 只需同步,0 只到 end_date)
        assert "覆盖率仅 0.0%" in msg
        # total_synced>0(有历史补数据,但非当日)
        assert "total_synced=" in msg
        assert "total_synced=0" not in msg  # 不是全空

    async def test_normal_sync_not_raises(self):
        """正常同步:大部分 symbol 有 end_date 数据 → 覆盖率高 → 不 raise."""
        service, provider, store, _, calendar = _make_service()

        store.get_last_sync_dates = AsyncMock(
            return_value={
                "600000.SH": date(2024, 1, 10),
                "600001.SH": date(2024, 1, 10),
            }
        )
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()
        # 两只都返 end_date(1/31)数据
        provider.get_kline = AsyncMock(
            return_value=[
                _make_bar("600000.SH", datetime(2024, 1, 31)),
                _make_bar("600001.SH", datetime(2024, 1, 31)),
            ]
        )
        calendar.get_trading_days = AsyncMock(
            return_value=[date(2024, 1, 31)]
        )

        result = await service.sync(
            symbols=["600000.SH", "600001.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )
        # 不 raise,正常返回
        assert result.synced_records == 2
        assert result.success_count == 2

    async def test_low_coverage_raises(self):
        """覆盖率 < 10%(11 只仅 1 只有数据 = 9.09%)→ raise."""
        service, provider, store, _, calendar = _make_service()

        # 11 只需同步,仅 1 只有 end_date 数据(覆盖率 9.09% < 10%)
        last_syncs = {f"60000{i}.SH": date(2024, 1, 10) for i in range(11)}
        store.get_last_sync_dates = AsyncMock(return_value=last_syncs)
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()
        # 仅 1 只返 end_date 数据,其余返空(停牌/返空)
        bars = [_make_bar("600000.SH", datetime(2024, 1, 31))]
        provider.get_kline = AsyncMock(return_value=bars)
        calendar.get_trading_days = AsyncMock(
            return_value=[date(2024, 1, 31)]
        )

        with pytest.raises(EmptyResponseError) as exc_info:
            await service.sync(
                symbols=list(last_syncs.keys()),
                interval=Interval.DAY,
                start="20240101",
                end="20240131",
            )
        msg = str(exc_info.value)
        assert "覆盖率仅 9.1%" in msg

    async def test_empty_response_holiday_silent(self):
        """全 chunk 返空 + end 非交易日(节假日)→ 不 raise,正常 return."""
        service, provider, store, _, calendar = _make_service()

        store.get_last_sync_dates = AsyncMock(
            return_value={"600000.SH": date(2024, 1, 10)}
        )
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()
        provider.get_kline = AsyncMock(return_value=[])
        # calendar 全返空(end 非交易日 + 窗口无交易日)
        calendar.get_trading_days = AsyncMock(return_value=[])

        result = await service.sync(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )
        # 不 raise,返回正常 SyncResult
        assert result.synced_records == 0
        assert result.success_count == 1
        # calendar 被查询(end 单点 + 窗口,2 次)
        assert calendar.get_trading_days.call_count == 2

    async def test_no_sync_needed_skips_detection(self):
        """symbols_needing_sync=0(数据已最新)→ 不进检测,不 raise."""
        service, provider, store, _, calendar = _make_service()

        store.get_last_sync_dates = AsyncMock(
            return_value={"600000.SH": date(2024, 1, 31)}
        )
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()
        provider.get_kline = AsyncMock(return_value=[])
        calendar.get_trading_days = AsyncMock(return_value=[date(2024, 1, 31)])

        result = await service.sync(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )
        # 不 raise(因 symbols_needing_sync=0,不进检测分支)
        assert result.synced_records == 0
        # calendar 不应被查询(提前 return)
        calendar.get_trading_days.assert_not_called()

    async def test_api_failure_with_trading_days_raises(self):
        """全 API 异常失败 + end 是交易日 → 也 raise(覆盖率 0%)."""
        service, provider, store, _, calendar = _make_service()

        store.get_last_sync_dates = AsyncMock(
            return_value={"600000.SH": date(2024, 1, 10)}
        )
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()
        provider.get_kline = AsyncMock(side_effect=Exception("API error"))
        calendar.get_trading_days = AsyncMock(
            return_value=[date(2024, 1, 31)]
        )

        with pytest.raises(EmptyResponseError):
            await service.sync(
                symbols=["600000.SH"],
                interval=Interval.DAY,
                start="20240101",
                end="20240131",
            )

    async def test_end_non_trading_with_data_not_raises(self):
        """end 非交易日(周末)+ 有历史补数据 → 不 raise(走 elif 的 else)."""
        service, provider, store, _, calendar = _make_service()

        store.get_last_sync_dates = AsyncMock(
            return_value={"600000.SH": date(2024, 1, 10)}
        )
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()
        # 返历史数据(< end_date,非当日)
        provider.get_kline = AsyncMock(
            return_value=[_make_bar("600000.SH", datetime(2024, 1, 25))]
        )
        # end=1/31 非交易日(模拟周末)
        calendar.get_trading_days = AsyncMock(return_value=[])

        result = await service.sync(
            symbols=["600000.SH"],
            interval=Interval.DAY,
            start="20240101",
            end="20240131",
        )
        # 不 raise(end 非交易日 + total_synced>0,走 elif 的 else,无 raise)
        assert result.synced_records == 1

    async def test_week_with_data_not_raises(self):
        """week 周期 + 有数据(max_date=周期首日 < end_date)→ 不 raise.

        回归 2026-08-15 kline_week W33 误判案例:AM week 周期线 trade_time
        是周期首交易日(周一),end_date 是周期末日(周五),覆盖率检测的
        `max_date >= end_date` 永不成立 → 拉到 15442 条周线却判 0% 覆盖,
        重试 7 次浪费 7.5h。修复:覆盖率检测仅对 DAY 周期,长周期只查全空。
        """
        service, provider, store, _, calendar = _make_service()

        store.get_last_sync_dates = AsyncMock(
            return_value={"600000.SH": date(2024, 1, 5)}
        )
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()
        # 周线数据 trade_time = 周一(周期首日),end=1/12(周五,周期末日)
        provider.get_kline = AsyncMock(
            return_value=[_make_bar("600000.SH", datetime(2024, 1, 8))]
        )
        # 窗口含交易日(用于全空检查的 calendar 查询)
        calendar.get_trading_days = AsyncMock(
            return_value=[date(2024, 1, 8)]
        )

        result = await service.sync(
            symbols=["600000.SH"],
            interval=Interval.WEEK,
            start="20240101",
            end="20240112",  # 周五,W2 末日;周线 trade_time=1/8 周一
        )
        # 不 raise:week 有数据(total_synced=1),跳过覆盖率检测,全空检查不触发
        assert result.synced_records == 1
        assert result.success_count == 1

    async def test_week_empty_raises(self):
        """week 周期 + 全空 + 窗口含交易日 → raise(长周期全空仍要检测)."""
        service, provider, store, _, calendar = _make_service()

        store.get_last_sync_dates = AsyncMock(
            return_value={"600000.SH": date(2024, 1, 5)}
        )
        store.save_kline = AsyncMock()
        store.set_last_sync_dates = AsyncMock()
        provider.get_kline = AsyncMock(return_value=[])  # 全空
        calendar.get_trading_days = AsyncMock(
            return_value=[date(2024, 1, 8)]
        )

        with pytest.raises(EmptyResponseError) as exc_info:
            await service.sync(
                symbols=["600000.SH"],
                interval=Interval.WEEK,
                start="20240101",
                end="20240112",
            )
        # 走全空分支(窗口含交易日但 0 条)
        msg = str(exc_info.value)
        assert "0 条入库" in msg
