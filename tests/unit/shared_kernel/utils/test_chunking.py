"""chunking 模块单元测试 — 纯内存预算模型(无 API symbols cap)。

核心公式:chunk_size = batch_rows / 每 symbol 行数
每 symbol 行数 = 窗口天数 / 周期单位交易日数
conftest mock get_config 返回 default,故 api_batch_rows 默认 1580000。
"""

from unittest.mock import patch

import pytest

from galaxy_core.shared_kernel.utils import chunking
from galaxy_core.shared_kernel.utils.chunking import (
    KLINE_INTERVAL_TRADING_DAYS,
    resolve_daily_chunk_size,
    resolve_kline_chunk_size,
    resolve_weight_chunk_size,
)

# 全量窗口:20130101 ~ 20260708 ≈ 13.5 年 ≈ 4934 天
FULL_START = "20130101"
FULL_END = "20260708"
# 增量窗口:20260707 ~ 20260708 = 1 天
INCR_START = "20260707"
INCR_END = "20260708"


class TestResolveKlineChunkSize:
    """K 线:按窗口 + 周期估算 每 symbol 行数,反推 chunk_size(内存预算 + kline_code_cap)。"""

    def test_full_day_320(self):
        """全量 day(4934行/只):158万/4934 = 320(预算主导,低于 cap 500 不截断)。"""
        assert resolve_kline_chunk_size("day", FULL_START, FULL_END) == 320

    def test_full_week_1600_capped(self):
        """全量 week(987行/只):158万/987 = 1600,被 kline_code_cap=500 拦下(2026-08-06:
        SDK 对 3000+ 只 code_list 不稳定,week 稀疏也不再放大到 1600)。"""
        assert resolve_kline_chunk_size("week", FULL_START, FULL_END) == 500

    def test_full_week_larger_than_day(self):
        """全量 week chunk > day chunk(数据稀疏自动放大,但 cap 截断)。"""
        day = resolve_kline_chunk_size("day", FULL_START, FULL_END)
        week = resolve_kline_chunk_size("week", FULL_START, FULL_END)
        assert week > day

    def test_full_month_capped_500(self):
        """全量 month(246行/只):158万/246 = 6422,被 cap 拦到 500。"""
        week = resolve_kline_chunk_size("week", FULL_START, FULL_END)
        month = resolve_kline_chunk_size("month", FULL_START, FULL_END)
        assert month == 500 == week

    def test_full_year_capped_500(self):
        """全量 year(20行/只):158万/20 = 79000,被 cap 拦到 500。"""
        assert resolve_kline_chunk_size("year", FULL_START, FULL_END) == 500

    def test_incremental_day_capped_500(self):
        """增量 day(1行/只):158万/1 = 158 万,被 cap 拦到 500/批。
        (2026-08-06:原不分批导致混合市场静默丢沪深 + 单市场大组卡死)"""
        assert resolve_kline_chunk_size("day", INCR_START, INCR_END) == 500

    def test_incremental_all_intervals_same_cap(self):
        """增量(1天):所有周期 rows_per_symbol=1 → chunk 都 = 158 万,被 cap 拦到 500。"""
        for interval in ("day", "week", "month", "season", "year"):
            assert resolve_kline_chunk_size(interval, INCR_START, INCR_END) == 500

    def test_unknown_interval_treated_as_day(self):
        """未知周期 → trading_days_per_unit 默认 1(等同 day)。"""
        assert resolve_kline_chunk_size("min5", FULL_START, FULL_END) == \
            resolve_kline_chunk_size("day", FULL_START, FULL_END)

    def test_config_override_changes_base(self):
        """mock api_batch_rows=100000 → 全量 day:100000/4934 = 20。"""
        with patch.object(chunking, "get_config", return_value=100000):
            assert resolve_kline_chunk_size("day", FULL_START, FULL_END) == 20

    def test_invalid_config_falls_back(self):
        """非正整数配置 → batch_rows 回退 1580000,cap 回退 500,增量 day = 500。"""
        with patch.object(chunking, "get_config", return_value=-1):
            assert resolve_kline_chunk_size("day", INCR_START, INCR_END) == 500

    def test_all_intervals_in_trading_days_table(self):
        """交易日表覆盖所有日级以上周期。"""
        for interval in ("day", "week", "month", "season", "year"):
            assert interval in KLINE_INTERVAL_TRADING_DAYS

    def test_minimum_chunk_is_1(self):
        """极小预算 + 极大窗口 → chunk 下限 1。"""
        with patch.object(chunking, "get_config", return_value=1):
            assert resolve_kline_chunk_size("day", FULL_START, FULL_END) == 1


class TestResolveDailyChunkSize:
    """日度行情类(非 K 线):industry_daily — 内存预算 + codes cap 双约束。

    2026-07-17:新增 daily_code_cap(默认 100),小窗口被 cap 拦下避免 SDK 大批量
    codes 卡死/返空(实测 7 天窗口算出 22 万导致 industry_daily 0 条)。
    """

    def test_full_window_capped_at_100(self):
        """全量(4934天):内存预算 158万/4934 = 320 > cap 100 → cap 主导,返 100。"""
        assert resolve_daily_chunk_size(FULL_START, FULL_END) == 100

    def test_small_window_capped_at_100(self):
        """增量(1天):158万/1 = 158 万 → cap 拦到 100(不再不分批)。

        回归 2026-07-17:旧版无 cap 返 158 万,SDK 一次传大批 codes 卡死。
        """
        assert resolve_daily_chunk_size(INCR_START, INCR_END) == 100

    def test_week_window_capped_at_100(self):
        """7 天窗口:158万/7 ≈ 22 万 → cap 拦到 100(industry_daily 实锤场景)."""
        assert resolve_daily_chunk_size("20260710", "20260716") == 100

    def test_large_budget_override_small_window_still_capped(self):
        """mock 预算 = 10000,增量(1天)→ min(10000//1, cap=100) = 100(cap 主导).

        patch get_config 整体返 10000 → 两个 _read 都返 10000,
        min(10000, 10000)=10000 不对...实际需 side_effect 按 key 区分。
        这里用 side_effect:api_batch_rows 返 10000,daily_code_cap 返 default(100)。
        """
        def fake_get(section, key, default=None):
            if key == "api_batch_rows":
                return 10000
            return default  # daily_code_cap 返默认 100
        with patch.object(chunking, "get_config", side_effect=fake_get):
            assert resolve_daily_chunk_size(INCR_START, INCR_END) == 100

    def test_small_budget_dominant_below_cap(self):
        """mock 预算 = 100,全量(4934天)→ max(1, 100/4934) = 1 < cap → 1(内存主导)."""
        def fake_get(section, key, default=None):
            if key == "api_batch_rows":
                return 100
            return default  # cap 默认 100
        with patch.object(chunking, "get_config", side_effect=fake_get):
            assert resolve_daily_chunk_size(FULL_START, FULL_END) == 1

    def test_cap_override(self):
        """mock daily_code_cap = 50,增量(1天)→ min(158万, 50) = 50."""
        def fake_get(section, key, default=None):
            if key == "daily_code_cap":
                return 50
            return default  # api_batch_rows 返默认 158 万
        with patch.object(chunking, "get_config", side_effect=fake_get):
            assert resolve_daily_chunk_size(INCR_START, INCR_END) == 50

    def test_invalid_cap_falls_back(self):
        """非正整数 cap → 回退默认 100,增量(1天)→ 100。"""
        def fake_get(section, key, default=None):
            if key == "daily_code_cap":
                return -1
            return default
        with patch.object(chunking, "get_config", side_effect=fake_get):
            assert resolve_daily_chunk_size(INCR_START, INCR_END) == 100


class TestResolveWeightChunkSize:
    """成分股二维展开类:独立小基准(默认 20 指数/批)。"""

    def test_returns_default(self):
        """默认 20(conftest mock get_config 返回 default=20)。"""
        assert resolve_weight_chunk_size() == 20

    def test_config_override(self):
        """mock 返回 50 → 50。"""
        with patch.object(chunking, "get_config", return_value=50):
            assert resolve_weight_chunk_size() == 50

    def test_invalid_falls_back(self):
        """非正整数 → 回退 20。"""
        with patch.object(chunking, "get_config", return_value=0):
            assert resolve_weight_chunk_size() == 20
