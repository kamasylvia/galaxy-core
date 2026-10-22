"""Tests for vectorized kline operations.

验证 parse_trade_time_vectorized 和 extract_records_vectorized 的正确性，
以及与旧 iterrows 实现的等价性。
"""

import numpy as np
import pandas as pd
import pytest
from datetime import date, datetime

from galaxy_core.database.services.kline import (
    extract_row_values,
    parse_trade_time,
    parse_trade_time_vectorized,
)


class TestParseTradeTimeVectorized:
    """Tests for parse_trade_time_vectorized function."""

    def test_datetime_series_passthrough(self):
        """输入 datetime Series → 输出不变."""
        from galaxy_core.database.services.kline import parse_trade_time_vectorized

        input_series = pd.Series([datetime(2025, 1, 15), datetime(2025, 1, 16)])
        result, errors = parse_trade_time_vectorized(input_series)
        assert len(errors) == 0
        assert result.iloc[0].date() == date(2025, 1, 15)
        assert result.iloc[1].date() == date(2025, 1, 16)

    def test_string_yyyymmdd_series(self):
        """输入 str '20250115' Series → 输出 datetime(2025,1,15)."""
        from galaxy_core.database.services.kline import parse_trade_time_vectorized

        input_series = pd.Series(["20250115", "20250116"])
        result, errors = parse_trade_time_vectorized(input_series)
        assert len(errors) == 0
        assert result.iloc[0].date() == date(2025, 1, 15)
        assert result.iloc[1].date() == date(2025, 1, 16)

    def test_int_yyyymmdd_series(self):
        """输入 int 20250115 Series → 输出 datetime(2025,1,15)."""
        from galaxy_core.database.services.kline import parse_trade_time_vectorized

        input_series = pd.Series([20250115, 20250116])
        result, errors = parse_trade_time_vectorized(input_series)
        assert len(errors) == 0
        assert result.iloc[0].date() == date(2025, 1, 15)
        assert result.iloc[1].date() == date(2025, 1, 16)

    def test_mixed_types_with_errors(self):
        """输入混合类型（str/int/NaN）→ 正常解析的保留，异常的分离到 errors."""
        from galaxy_core.database.services.kline import parse_trade_time_vectorized

        input_series = pd.Series(["20250115", 20250116, "invalid", np.nan])
        fallback = pd.Series([datetime(2025, 1, 13), datetime(2025, 1, 14), datetime(2025, 1, 17), datetime(2025, 1, 18)])
        result, errors = parse_trade_time_vectorized(input_series, fallback_series=fallback)
        assert result.iloc[0].date() == date(2025, 1, 15)
        assert result.iloc[1].date() == date(2025, 1, 16)
        # "invalid" uses fallback
        assert result.iloc[2].date() == date(2025, 1, 17)
        # NaN uses fallback
        assert result.iloc[3].date() == date(2025, 1, 18)

    def test_nan_with_fallback(self):
        """输入 NaN/None → 使用 fallback（idx 值）."""
        from galaxy_core.database.services.kline import parse_trade_time_vectorized

        input_series = pd.Series([None, np.nan])
        fallback = pd.Series([datetime(2025, 1, 15), datetime(2025, 1, 16)])
        result, errors = parse_trade_time_vectorized(input_series, fallback_series=fallback)
        assert result.iloc[0].date() == date(2025, 1, 15)
        assert result.iloc[1].date() == date(2025, 1, 16)

    def test_nan_without_fallback_marks_error(self):
        """输入 NaN 且无 fallback → 标记为 error."""
        from galaxy_core.database.services.kline import parse_trade_time_vectorized

        input_series = pd.Series([np.nan])
        result, errors = parse_trade_time_vectorized(input_series, fallback_series=None)
        assert len(errors) == 1
        assert 0 in errors

    def test_string_date_dash_format(self):
        """输入 str '2025-01-15' Series → 输出 datetime(2025,1,15)."""
        from galaxy_core.database.services.kline import parse_trade_time_vectorized

        input_series = pd.Series(["2025-01-15", "2025-01-16"])
        result, errors = parse_trade_time_vectorized(input_series)
        assert len(errors) == 0
        assert result.iloc[0].date() == date(2025, 1, 15)
        assert result.iloc[1].date() == date(2025, 1, 16)

    def test_rangeindex_fallback_not_treated_as_nanoseconds(self):
        """fallback 是 RangeIndex（整数行号 0,1,2）时不应被当 nanoseconds 解析成 1970-01-01.

        回归：batch_save_kline_to_db 第 457 行 fallback = df.index，当 kline_time
        全 NaN 且 df 为默认 RangeIndex 时，旧代码崩溃（dtype 冲突）且误报 1970 日期。
        """
        from galaxy_core.database.services.kline import parse_trade_time_vectorized

        df = pd.DataFrame({"kline_time": [None, None, None]})
        result, errors = parse_trade_time_vectorized(
            df["kline_time"], fallback_series=df.index
        )
        # 全部应为 NaT（fallback 无日期语义，不应假成功为 1970-01-01）
        assert errors == [0, 1, 2]
        for v in result:
            assert pd.isna(v), f"应为 NaT，得到 {v}"

    def test_fallback_accepts_index_object(self):
        """fallback_series 传 pd.Index（非 Series）时应正常工作，不报 AttributeError."""
        from galaxy_core.database.services.kline import parse_trade_time_vectorized

        df = pd.DataFrame(
            {"kline_time": ["20240101", None, "20240103"]},
            index=["20240101", "20240102", "20240103"],
        )
        result, errors = parse_trade_time_vectorized(
            df["kline_time"], fallback_series=df.index
        )
        assert errors == []
        assert result.iloc[0].date() == date(2024, 1, 1)
        assert result.iloc[1].date() == date(2024, 1, 2)
        assert result.iloc[2].date() == date(2024, 1, 3)

    def test_fallback_unparseable_value_marked_error(self):
        """fallback 值存在但解析失败（如 'garbage'）→ 标记到 errors，不崩溃."""
        from galaxy_core.database.services.kline import parse_trade_time_vectorized

        df = pd.DataFrame(
            {"kline_time": ["20240101", None]},
            index=["20240101", "garbage"],
        )
        result, errors = parse_trade_time_vectorized(
            df["kline_time"], fallback_series=df.index
        )
        assert result.iloc[0].date() == date(2024, 1, 1)
        assert pd.isna(result.iloc[1])
        assert errors == ["garbage"]


    def test_large_dataframe_performance(self):
        """超大 DataFrame 不崩溃."""
        from galaxy_core.database.services.kline import parse_trade_time_vectorized

        n = 10000
        dates = [f"202501{(i % 28) + 1:02d}" for i in range(n)]
        input_series = pd.Series(dates)
        result, errors = parse_trade_time_vectorized(input_series)
        assert len(result) == n
        assert len(errors) == 0


class TestExtractRecordsVectorized:
    """Tests for extract_records_vectorized function."""

    def test_standard_ohlcv_dataframe(self):
        """输入标准 OHLCV DataFrame → 输出 List[dict] 与旧 extract_row_values 一致."""
        from galaxy_core.database.services.kline import extract_records_vectorized

        df = pd.DataFrame(
            {
                "open": [10.5, 11.0],
                "high": [11.0, 11.5],
                "low": [10.0, 10.5],
                "close": [10.8, 11.2],
                "volume": [1000000, 1100000],
                "amount": [10500000.0, 11500000.0],
            },
            index=[datetime(2025, 1, 15), datetime(2025, 1, 16)],
        )

        records = extract_records_vectorized(df)
        assert len(records) == 2
        assert records[0]["open"] == 10.5
        assert records[0]["volume"] == 1000000
        assert records[1]["close"] == 11.2

    def test_nan_columns_produce_none(self):
        """输入含 NaN 的列 → 对应字段为 None."""
        from galaxy_core.database.services.kline import extract_records_vectorized

        df = pd.DataFrame(
            {
                "open": [10.5, np.nan],
                "high": [11.0, 11.5],
                "low": [10.0, 10.5],
                "close": [10.8, np.nan],
                "volume": [1000000, np.nan],
                "amount": [10500000.0, np.nan],
            },
            index=[datetime(2025, 1, 15), datetime(2025, 1, 16)],
        )

        records = extract_records_vectorized(df)
        assert records[1]["open"] is None
        assert records[1]["close"] is None
        assert records[1]["volume"] is None
        assert records[1]["amount"] is None

    def test_volume_float_to_int(self):
        """输入 volume 为 float → 转为 int."""
        from galaxy_core.database.services.kline import extract_records_vectorized

        df = pd.DataFrame(
            {
                "open": [10.5],
                "high": [11.0],
                "low": [10.0],
                "close": [10.8],
                "volume": [1000000.0],
                "amount": [10500000.0],
            },
            index=[datetime(2025, 1, 15)],
        )

        records = extract_records_vectorized(df)
        assert records[0]["volume"] == 1000000
        assert isinstance(records[0]["volume"], int)

    def test_all_nan_column(self):
        """全 NaN 列 → 对应字段全部为 None."""
        from galaxy_core.database.services.kline import extract_records_vectorized

        df = pd.DataFrame(
            {
                "open": [np.nan, np.nan],
                "high": [11.0, 11.5],
                "low": [10.0, 10.5],
                "close": [10.8, 11.2],
                "volume": [1000000, 1100000],
                "amount": [10500000.0, 11500000.0],
            },
            index=[datetime(2025, 1, 15), datetime(2025, 1, 16)],
        )

        records = extract_records_vectorized(df)
        assert records[0]["open"] is None
        assert records[1]["open"] is None


class TestBatchSaveEquivalence:
    """Tests comparing old iterrows logic with new vectorized logic."""

    def test_equivalence_standard_input(self):
        """相同 DataFrame 输入，旧 iterrows 逻辑和新向量化逻辑产生完全相同的 records 列表."""
        from galaxy_core.database.services.kline import extract_records_vectorized

        df = pd.DataFrame(
            {
                "open": [10.5, 11.0, 12.0],
                "high": [11.0, 11.5, 12.5],
                "low": [10.0, 10.5, 11.5],
                "close": [10.8, 11.2, 12.2],
                "volume": [1000000, 1100000, 1200000],
                "amount": [10500000.0, 11500000.0, 12500000.0],
            },
            index=[datetime(2025, 1, 15), datetime(2025, 1, 16), datetime(2025, 1, 17)],
        )

        # Old: iterrows
        old_records = []
        for _, row in df.iterrows():
            old_records.append(extract_row_values(row))

        # New: vectorized
        new_records = extract_records_vectorized(df)

        assert len(old_records) == len(new_records)
        for old, new in zip(old_records, new_records):
            assert old == new, f"Mismatch: old={old}, new={new}"

    def test_equivalence_with_nan_values(self):
        """含 NaN 输入的等价性."""
        from galaxy_core.database.services.kline import extract_records_vectorized

        df = pd.DataFrame(
            {
                "open": [10.5, np.nan],
                "high": [11.0, 11.5],
                "low": [10.0, 10.5],
                "close": [np.nan, 11.2],
                "volume": [1000000, np.nan],
                "amount": [np.nan, 11500000.0],
            },
            index=[datetime(2025, 1, 15), datetime(2025, 1, 16)],
        )

        # Old: iterrows
        old_records = []
        for _, row in df.iterrows():
            old_records.append(extract_row_values(row))

        # New: vectorized
        new_records = extract_records_vectorized(df)

        assert len(old_records) == len(new_records)
        for old, new in zip(old_records, new_records):
            assert old == new, f"Mismatch: old={old}, new={new}"

    def test_equivalence_parse_trade_time(self):
        """parse_trade_time 向量化版本与旧版对相同输入产生相同输出."""
        from galaxy_core.database.services.kline import parse_trade_time_vectorized

        values = [datetime(2025, 1, 15), "20250116", 20250117]
        fallbacks = [datetime(2025, 1, 13), datetime(2025, 1, 14), datetime(2025, 1, 18)]

        # Old: per-element
        old_results = []
        for v, idx in zip(values, fallbacks):
            old_results.append(parse_trade_time(v, idx))

        # New: vectorized
        input_series = pd.Series(values)
        fallback_series = pd.Series(fallbacks)
        new_series, errors = parse_trade_time_vectorized(input_series, fallback_series=fallback_series)

        assert len(errors) == 0
        for i, (old, new) in enumerate(zip(old_results, new_series)):
            assert old == new, f"Row {i}: old={old}, new={new}"


class TestParseTradeTimeCSTTimezone:
    """2026-07-17 timestamptz 改造回归:parse_trade_time 系列必须返回北京时区 aware datetime.

    SDK 字面值是北京 wall-clock,parse 入口 attach CST tzinfo 防 timestamptz 列把
    naive 当 UTC 写入(偏移 8 小时)。
    """

    def test_parse_trade_time_returns_cst_aware(self):
        """单值 parse_trade_time 返回 CST aware."""
        from galaxy_core.shared_kernel.utils.constants import CST

        result = parse_trade_time("20250115")
        assert result.tzinfo is not None
        assert result.tzinfo == CST
        # wall-clock 不变(2025-01-15 00:00 北京)
        assert result.year == 2025 and result.month == 1 and result.day == 15

    def test_parse_trade_time_vectorized_returns_cst_aware(self):
        """向量化版本返回 CST aware Series."""
        from galaxy_core.shared_kernel.utils.constants import CST

        input_series = pd.Series([datetime(2025, 1, 15), "20250116"])
        result, errors = parse_trade_time_vectorized(input_series)
        assert len(errors) == 0
        assert result.dt.tz is not None
        assert str(result.dt.tz) == "Asia/Shanghai"

    def test_parse_trade_time_naive_input_localized(self):
        """naive datetime 输入被 localize 到 CST(不改 wall-clock)."""
        from galaxy_core.shared_kernel.utils.constants import CST

        naive = datetime(2025, 1, 15, 9, 30)
        result = parse_trade_time(naive)
        assert result.tzinfo == CST
        # wall-clock 保持 09:30
        assert result.hour == 9 and result.minute == 30
