"""Tests for vectorized reference data operations.

验证 _parse_stock_basic_records, _parse_backward_factor_records 的正确性，以及与旧 iterrows 实现的等价性。
"""

import numpy as np
import pandas as pd
import pytest
from datetime import date, datetime

from galaxy_core.application.scheduler.reference_data_sync_job import ReferenceDataSyncJob


class TestParseStockBasicRecords:
    """Tests for _parse_stock_basic_records classmethod."""

    def test_standard_input(self):
        """输入含 MARKET_CODE/SECURITY_NAME/LISTDATE 的 DataFrame → 输出正确 records."""
        df = pd.DataFrame(
            {
                "MARKET_CODE": ["600000.SH", "000001.SZ"],
                "SECURITY_NAME": ["浦发银行", "平安银行"],
                "COMP_NAME": ["浦发银行股份有限公司", "平安银行股份有限公司"],
                "PINYIN": ["PFYH", "PAYH"],
                "LISTDATE": ["19991110", "19910403"],
                "DELISTDATE": [None, None],
            }
        )

        records = ReferenceDataSyncJob._parse_stock_basic_records(df, "EXTRA_ETF")
        assert len(records) == 2
        assert records[0]["symbol"] == "600000.SH"
        assert records[0]["security_name"] == "浦发银行"
        assert records[0]["list_date"] == date(1999, 11, 10)
        assert records[0]["delist_date"] is None
        assert records[0]["security_type"] == "EXTRA_ETF"

    def test_nan_listdate_produces_none(self):
        """输入含 NaN LISTDATE → list_date 为 None."""
        df = pd.DataFrame(
            {
                "MARKET_CODE": ["600000.SH"],
                "SECURITY_NAME": ["浦发银行"],
                "LISTDATE": [np.nan],
                "DELISTDATE": [None],
            }
        )

        records = ReferenceDataSyncJob._parse_stock_basic_records(df, "EXTRA_ETF")
        assert len(records) == 1
        assert records[0]["list_date"] is None

    def test_code_column_fallback(self):
        """支持 code 列名（非 MARKET_CODE）."""
        df = pd.DataFrame(
            {
                "code": ["600000.SH"],
                "SECURITY_NAME": ["浦发银行"],
                "LISTDATE": ["19991110"],
            }
        )

        records = ReferenceDataSyncJob._parse_stock_basic_records(df, "EXTRA_ETF")
        assert len(records) == 1
        assert records[0]["symbol"] == "600000.SH"

    def test_skips_nan_code(self):
        """跳过 code 为 None/NaN 的行."""
        df = pd.DataFrame(
            {
                "MARKET_CODE": ["600000.SH", None, "000001.SZ"],
                "SECURITY_NAME": ["浦发银行", "未知", "平安银行"],
                "LISTDATE": ["19991110", "20000101", "19910403"],
            }
        )

        records = ReferenceDataSyncJob._parse_stock_basic_records(df, "EXTRA_ETF")
        assert len(records) == 2
        assert records[0]["symbol"] == "600000.SH"
        assert records[1]["symbol"] == "000001.SZ"

    def test_handles_duplicate_index_labels(self):
        """SDK 返回的 DataFrame 可能含重复 index 标签（实测 get_stock_basic 对股票
        返回 index 全为 0），boolean mask 索引不应触发 'cannot reindex on an axis
        with duplicate labels'。回归 AGENTS.md 2026-07-07。
        """
        df = pd.DataFrame(
            {
                "MARKET_CODE": ["600000.SH", "000001.SZ"],
                "SECURITY_NAME": ["浦发银行", "平安银行"],
                "LISTDATE": ["19991110", "19910403"],
            },
            index=[0, 0],  # 模拟 SDK 返回的重复 index（实测真实结构）
        )

        records = ReferenceDataSyncJob._parse_stock_basic_records(df, "EXTRA_STOCK_A")

        assert len(records) == 2
        assert records[0]["symbol"] == "600000.SH"
        assert records[1]["symbol"] == "000001.SZ"

    def test_resets_index_with_many_duplicate_rows(self):
        """大量重复 index（如 5785 行全为同一 index 值）也能正确解析。"""
        n = 100
        df = pd.DataFrame(
            {
                "MARKET_CODE": [f"{i:06d}.SH" for i in range(n)],
                "SECURITY_NAME": [f"股票{i}" for i in range(n)],
                "LISTDATE": ["19991110"] * n,
            },
            index=[0] * n,  # 全部行 index 都是 0
        )

        records = ReferenceDataSyncJob._parse_stock_basic_records(df, "EXTRA_STOCK_A")

        assert len(records) == n
        assert records[0]["symbol"] == "000000.SH"
        assert records[99]["symbol"] == "000099.SH"

    def test_all_nan_object_column_becomes_none(self):
        """某 object 列全为 NaN（pandas 推断为 float64）→ records 中应为 None，
        不应残留 float('nan')。否则 asyncpg 报
        'invalid input: nan (expected str, got float)'。
        回归 2026-07-07 STOCK_A 补数遇到的 COMP_SNAME_ENG 全 NaN 问题。
        """
        df = pd.DataFrame(
            {
                "MARKET_CODE": ["600000.SH", "000001.SZ"],
                "SECURITY_NAME": ["浦发银行", "平安银行"],
                "COMP_NAME": ["c1", "c2"],
                "PINYIN": ["p1", "p2"],
                "COMP_NAME_ENG": ["e1", "e2"],
                "LISTPLATE_NAME": ["lp", "lp2"],
                "COMP_SNAME_ENG": [float("nan"), float("nan")],  # 全 NaN → float64
                "LISTDATE": ["19991110", "19910403"],
                "DELISTDATE": [None, None],
            }
        )
        # 确认测试前提：COMP_SNAME_ENG 列确实是 float64
        assert df["COMP_SNAME_ENG"].dtype == np.float64

        records = ReferenceDataSyncJob._parse_stock_basic_records(df, "EXTRA_STOCK_A")

        assert len(records) == 2
        for r in records:
            assert r["comp_sname_eng"] is None, f"期望 None，实际 {r['comp_sname_eng']!r}"
            assert not isinstance(r["comp_sname_eng"], float)


class TestParseRecordsFromCodeInfo:
    """Tests for _parse_records_from_code_info classmethod（ETF/INDEX 路径）."""

    def test_basic_etf_parsing(self):
        """get_code_info 风格 DataFrame（index=code_market, symbol=中文名, list_day）
        → 输出 11 字段对齐的 records。
        """
        df = pd.DataFrame(
            {
                "symbol": ["A50华宝", "粮食50"],
                "security_status": ["", ""],
                "pre_close": [1.0, 1.0],
                "high_limited": [1.1, 1.1],
                "low_limited": [0.9, 0.9],
                "price_tick": [0.001, 0.001],
                "list_day": ["20240318", "20240821"],
            },
            index=pd.Index(["159596.SZ", "159587.SZ"], name="code_market"),
        )

        records = ReferenceDataSyncJob._parse_records_from_code_info(
            df, "EXTRA_ETF", ["159596.SZ", "159587.SZ"]
        )

        assert len(records) == 2
        rec0 = next(r for r in records if r["symbol"] == "159596.SZ")
        assert rec0["security_name"] == "A50华宝"
        assert rec0["list_date"] == date(2024, 3, 18)
        assert rec0["delist_date"] is None
        assert rec0["security_type"] == "EXTRA_ETF"
        # 11 字段对齐（get_code_info 不提供的字段应为 None）
        assert rec0["comp_name"] is None
        assert rec0["pinyin"] is None
        assert rec0["comp_name_eng"] is None
        assert rec0["listplate_name"] is None
        assert rec0["comp_sname_eng"] is None
        assert rec0["is_listed"] is None

    def test_filters_to_requested_codes(self):
        """df 含 5 个 code，codes 列表只含 3 个 → 只输出 3 条。"""
        all_codes = [f"159{i:03d}.SZ" for i in range(5)]
        df = pd.DataFrame(
            {
                "symbol": [f"ETF{i}" for i in range(5)],
                "list_day": ["20240101"] * 5,
            },
            index=pd.Index(all_codes, name="code_market"),
        )
        requested = all_codes[:3]

        records = ReferenceDataSyncJob._parse_records_from_code_info(
            df, "EXTRA_ETF", requested
        )

        assert len(records) == 3
        output_symbols = {r["symbol"] for r in records}
        assert output_symbols == set(requested)

    def test_empty_dataframe_returns_empty_list(self):
        """空 DataFrame → 空列表，不 raise。"""
        df = pd.DataFrame(columns=["symbol", "list_day"])
        records = ReferenceDataSyncJob._parse_records_from_code_info(
            df, "EXTRA_ETF", ["159596.SZ"]
        )
        assert records == []

    def test_empty_codes_returns_empty_list(self):
        """codes 为空 → 空列表（不调 get_code_info 也无意义）。"""
        df = pd.DataFrame(
            {"symbol": ["A50华宝"], "list_day": ["20240318"]},
            index=pd.Index(["159596.SZ"], name="code_market"),
        )
        records = ReferenceDataSyncJob._parse_records_from_code_info(
            df, "EXTRA_ETF", []
        )
        assert records == []

    def test_missing_list_day_column_produces_none(self):
        """df 无 list_day 列 → list_date 为 None（不 raise）。"""
        df = pd.DataFrame(
            {"symbol": ["A50华宝"]},
            index=pd.Index(["159596.SZ"], name="code_market"),
        )
        records = ReferenceDataSyncJob._parse_records_from_code_info(
            df, "EXTRA_ETF", ["159596.SZ"]
        )
        assert len(records) == 1
        assert records[0]["list_date"] is None

    def test_nan_list_day_produces_none(self):
        """list_day 为 NaN → list_date 为 None。"""
        df = pd.DataFrame(
            {"symbol": ["A50华宝"], "list_day": [np.nan]},
            index=pd.Index(["159596.SZ"], name="code_market"),
        )
        records = ReferenceDataSyncJob._parse_records_from_code_info(
            df, "EXTRA_ETF", ["159596.SZ"]
        )
        assert len(records) == 1
        assert records[0]["list_date"] is None


class TestParseBackwardFactorRecords:
    """Tests for _parse_backward_factor_records classmethod."""

    def test_wide_format_dataframe(self):
        """输入宽格式 DataFrame（index=日期, columns=股票代码）→ melt 后输出正确 records."""
        df = pd.DataFrame(
            {
                "600000.SH": [1.0, 0.95],
                "000001.SZ": [1.0, 0.98],
            },
            index=pd.to_datetime(["2025-03-20", "2025-03-21"]),
        )

        records = ReferenceDataSyncJob._parse_backward_factor_records(df)
        assert len(records) == 4
        symbols = {r["symbol"] for r in records}
        assert symbols == {"600000.SH", "000001.SZ"}
        # Check dates(2026-07-17:trade_date 是 CST aware datetime,比较 date 部分)
        dates = {r["trade_date"] for r in records}
        assert dates == {date(2025, 3, 20), date(2025, 3, 21)}

    def test_nan_factor_skipped(self):
        """输入含 NaN factor → 该行跳过."""
        df = pd.DataFrame(
            {
                "600000.SH": [1.0, np.nan],
                "000001.SZ": [np.nan, 0.98],
            },
            index=pd.to_datetime(["2025-03-20", "2025-03-21"]),
        )

        records = ReferenceDataSyncJob._parse_backward_factor_records(df)
        assert len(records) == 2
        for r in records:
            assert not np.isnan(r["factor"])

    def test_factor_values_correct(self):
        """factor 值正确转换为 float."""
        df = pd.DataFrame(
            {"SYM_A": [1.0, 1.5, 2.0]},
            index=pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
        )

        records = ReferenceDataSyncJob._parse_backward_factor_records(df)
        factors = [r["factor"] for r in records]
        assert factors == [1.0, 1.5, 2.0]

    def test_empty_dataframe(self):
        """空 DataFrame → 空列表."""
        df = pd.DataFrame()

        records = ReferenceDataSyncJob._parse_backward_factor_records(df)
        assert records == []


class TestVectorizedHelpersEquivalence:
    """Tests comparing old scalar helpers with new vectorized versions."""

    def test_parse_date_equivalence(self):
        """_parse_date 向量化版与旧版对相同输入产生相同输出(date 部分).

        2026-08-26 nocodb 回迁:_parse_date_series 返回 date(与 _parse_date 一致)。
        """
        values = ["20250115", "2025-01-16", 20250117, None, np.nan, "invalid"]

        old_results = []
        for v in values:
            old_results.append(ReferenceDataSyncJob._parse_date(v))

        new_series = ReferenceDataSyncJob._parse_date_series(pd.Series(values))

        for i, (old, new) in enumerate(zip(old_results, new_series)):
            if old is None:
                assert pd.isna(new), f"Row {i}: old=None, new={new}"
            else:
                # nocodb 形态:new 即 date 对象,直接比较
                assert old == new, f"Row {i}: old={old}, new={new}"

    def test_to_float_equivalence(self):
        """_to_float 向量化版与旧版对相同输入产生相同输出."""
        values = [10.5, "10.5", None, np.nan, "invalid", 0]

        old_results = []
        for v in values:
            old_results.append(ReferenceDataSyncJob._to_float(v))

        new_series = ReferenceDataSyncJob._to_float_series(pd.Series(values))

        for i, (old, new) in enumerate(zip(old_results, new_series)):
            if old is None:
                assert pd.isna(new), f"Row {i}: old=None, new={new}"
            else:
                assert old == new, f"Row {i}: old={old}, new={new}"

    def test_to_bool_equivalence(self):
        """_to_bool 向量化版与旧版对相同输入产生相同输出."""
        values = [0, 1, "0", "1", None, np.nan, "invalid", True, False]

        old_results = []
        for v in values:
            old_results.append(ReferenceDataSyncJob._to_bool(v))

        new_series = ReferenceDataSyncJob._to_bool_series(pd.Series(values))

        for i, (old, new) in enumerate(zip(old_results, new_series)):
            assert old == new, f"Row {i}: old={old}, new={new}"
