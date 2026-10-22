"""Domain 层日期解析纯函数单元测试.

测试 date_range/parser.py 的纯函数行为。
"""

from datetime import datetime

from galaxy_core.domain.date_range.parser import (
    parse_date_to_int,
    int_to_datetime,
    datetime_to_int,
    expand_date_to_full,
    validate_date_length_for_interval,
    convert_date_string_to_int,
    validate_start_end_by_interval,
)


class TestParseDateToInt:
    """parse_date_to_int 测试."""

    def test_standard_date(self):
        """标准日期字符串."""
        assert parse_date_to_int("20230101") == 20230101

    def test_longer_string(self):
        """更长的字符串截取前8位."""
        assert parse_date_to_int("20230101123456") == 20230101


class TestIntToDatetime:
    """int_to_datetime 测试."""

    def test_standard_int(self):
        """标准整数日期."""
        assert int_to_datetime(20230101) == datetime(2023, 1, 1)


class TestDatetimeToInt:
    """datetime_to_int 测试."""

    def test_standard_datetime(self):
        """标准 datetime."""
        assert datetime_to_int(datetime(2023, 1, 1)) == 20230101


class TestExpandDateToFull:
    """expand_date_to_full 测试."""

    def test_year_start(self):
        """年线开始日期."""
        assert expand_date_to_full("2023", "year") == "20230101"

    def test_year_end(self):
        """年线结束日期."""
        assert expand_date_to_full("2023", "year", is_end=True) == "20231231"

    def test_month_start(self):
        """月线开始日期."""
        assert expand_date_to_full("202301", "month") == "20230101"

    def test_month_end(self):
        """月线结束日期."""
        assert expand_date_to_full("202301", "month", is_end=True) == "20230131"

    def test_day_passthrough(self):
        """日线直接返回."""
        assert expand_date_to_full("20230101", "day") == "20230101"

    def test_none_input(self):
        """None 输入返回 None."""
        assert expand_date_to_full(None, "day") is None

    def test_short_year_for_season(self):
        """季线只有年份."""
        assert expand_date_to_full("2023", "season") == "20230101"
        assert expand_date_to_full("2023", "season", is_end=True) == "20231231"


class TestValidateDateLengthForInterval:
    """validate_date_length_for_interval 测试."""

    def test_valid_day(self):
        """日线 8 位日期合法."""
        errors = validate_date_length_for_interval("20230101", "day")
        assert errors == []

    def test_invalid_day_length(self):
        """日线 2 位日期不合法."""
        errors = validate_date_length_for_interval("23", "day")
        assert len(errors) == 1
        assert "day" in errors[0]

    def test_valid_year(self):
        """年线 4 位合法."""
        errors = validate_date_length_for_interval("2023", "year")
        assert errors == []

    def test_none_input(self):
        """None 输入无错误."""
        errors = validate_date_length_for_interval(None, "day")
        assert errors == []


class TestConvertDateStringToInt:
    """convert_date_string_to_int 测试."""

    def test_year_start(self):
        """年线开始日期."""
        assert convert_date_string_to_int("2023", "year") == 20230101

    def test_year_end(self):
        """年线结束日期."""
        assert convert_date_string_to_int("2023", "year", is_end_date=True) == 20231231

    def test_month_start(self):
        """月线开始日期."""
        assert convert_date_string_to_int("202301", "month") == 20230101

    def test_month_end(self):
        """月线结束日期."""
        assert convert_date_string_to_int("202301", "month", is_end_date=True) == 20230131

    def test_day(self):
        """日线."""
        assert convert_date_string_to_int("20230101", "day") == 20230101


class TestValidateStartEndByInterval:
    """validate_start_end_by_interval 测试."""

    def test_passthrough(self):
        """原值返回."""
        start, end = validate_start_end_by_interval("day", "20230101", "20231231")
        assert start == "20230101"
        assert end == "20231231"

    def test_none_values(self):
        """None 值."""
        start, end = validate_start_end_by_interval("day", None, None)
        assert start is None
        assert end is None
