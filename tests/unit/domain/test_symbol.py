"""Domain 层 Symbol 纯函数单元测试.

测试 symbol 模块的纯函数行为。
"""

import pytest
from galaxy_core.domain.symbol.validator import (
    normalize_symbol,
    validate_symbol_format,
    is_code_suffix_match,
)
from galaxy_core.domain.symbol.type_inference import (
    infer_security_type,
    get_security_type_hierarchy,
    filter_most_precise_security_types,
)
from galaxy_core.domain.symbol.resolver import parse_symbols


class TestNormalizeSymbol:
    """normalize_symbol 测试."""

    def test_6digit_sh(self):
        """6位数字自动补 SH 后缀."""
        assert normalize_symbol("600000") == "600000.SH"
        assert normalize_symbol("510050") == "510050.SH"

    def test_6digit_sz(self):
        """6位数字自动补 SZ 后缀."""
        assert normalize_symbol("000001") == "000001.SZ"
        assert normalize_symbol("159915") == "159915.SZ"

    def test_6digit_bj(self):
        """6位数字自动补 BJ 后缀."""
        assert normalize_symbol("920001") == "920001.BJ"

    def test_already_has_suffix(self):
        """已有后缀直接返回."""
        assert normalize_symbol("600000.SH") == "600000.SH"
        assert normalize_symbol("000001.SZ") == "000001.SZ"

    def test_future_code(self):
        """期货代码."""
        assert normalize_symbol("IF2403") == "IF2403.FUTURE"


class TestValidateSymbolFormat:
    """validate_symbol_format 测试."""

    def test_6digit(self):
        """6位数字合法."""
        assert validate_symbol_format("600000") is True

    def test_security_type(self):
        """SecurityType 合法."""
        assert validate_symbol_format("SH_A") is True
        assert validate_symbol_format("SZ_ETF") is True

    def test_with_suffix(self):
        """带合法后缀合法."""
        assert validate_symbol_format("600000.SH") is True
        assert validate_symbol_format("000001.SZ") is True

    def test_invalid(self):
        """无效格式."""
        assert validate_symbol_format("invalid!") is False


class TestIsCodeSuffixMatch:
    """is_code_suffix_match 测试."""

    def test_sh_match(self):
        """SH 匹配."""
        assert is_code_suffix_match("600000", "SH") is True

    def test_sz_match(self):
        """SZ 匹配."""
        assert is_code_suffix_match("000001", "SZ") is True

    def test_no_match(self):
        """不匹配."""
        assert is_code_suffix_match("000001", "SH") is False


class TestInferSecurityType:
    """infer_security_type 测试."""

    def test_stock_sh(self):
        """上海股票."""
        assert infer_security_type("600000.SH") == "SH_A"

    def test_etf_sh(self):
        """上海 ETF."""
        assert infer_security_type("510050.SH") == "SH_ETF"

    def test_sz_stock_000_prefix(self):
        """深圳000开头应为A股而非指数."""
        assert infer_security_type("000001.SZ") == "SZ_A"
        assert infer_security_type("000002.SZ") == "SZ_A"
        assert infer_security_type("000063.SZ") == "SZ_A"

    def test_sz_index_399_prefix(self):
        """深圳399开头应为指数."""
        assert infer_security_type("399001.SZ") == "SZ_INDEX"
        assert infer_security_type("399006.SZ") == "SZ_INDEX"

    def test_sh_index_000_prefix(self):
        """上海000开头应为指数."""
        assert infer_security_type("000001.SH") == "SH_INDEX"

    def test_security_type_input(self):
        """SecurityType 输入直接返回."""
        assert infer_security_type("SH_A") == "SH_A"

    def test_unknown(self):
        """无法推断返回 None."""
        assert infer_security_type("unknown") is None


class TestGetSecurityTypeHierarchy:
    """get_security_type_hierarchy 测试."""

    def test_hierarchy_structure(self):
        """层级关系结构正确."""
        hierarchy = get_security_type_hierarchy()
        assert "EXTRA_ETF" in hierarchy
        assert "SH_ETF" in hierarchy["EXTRA_ETF"]
        assert "SZ_ETF" in hierarchy["EXTRA_ETF"]


class TestFilterMostPreciseSecurityTypes:
    """filter_most_precise_security_types 测试."""

    def test_filter_parent_child(self):
        """过滤父子关系."""
        result = filter_most_precise_security_types(["EXTRA_STOCK_A", "SH_A"])
        assert result == ["EXTRA_STOCK_A"]

    def test_no_filter_parallel(self):
        """并列关系不过滤."""
        result = filter_most_precise_security_types(["SH_A", "SZ_A"])
        assert set(result) == {"SH_A", "SZ_A"}


class TestParseSymbols:
    """parse_symbols 测试."""

    def test_single_symbol(self):
        """单个代码."""
        result = parse_symbols("600000.SH")
        assert result == [("symbol", "600000.SH")]

    def test_list_format(self):
        """列表格式."""
        result = parse_symbols("[600000, 000001]")
        assert len(result) == 2
        assert ("symbol", "600000.SH") in result
        assert ("symbol", "000001.SZ") in result

    def test_security_type(self):
        """SecurityType."""
        result = parse_symbols("SH_A")
        assert result == [("security_type", "SH_A")]

    def test_mixed(self):
        """混合列表."""
        result = parse_symbols("600000, SH_ETF")
        assert len(result) == 2
        assert ("symbol", "600000.SH") in result
        assert ("security_type", "SH_ETF") in result

    def test_invalid_raises(self):
        """无效格式应抛出 ValueError."""
        with pytest.raises(ValueError):
            parse_symbols("invalid!")
