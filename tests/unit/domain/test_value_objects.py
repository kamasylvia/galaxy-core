"""Domain 层值对象单元测试.

测试 Interval、SecurityType 枚举以及 dataclass 值对象的纯函数行为。
"""

from datetime import date, datetime

import pytest

from galaxy_core.domain.value_objects import (
    BackwardFactor,
    IndexConstituent,
    IndexWeight,
    IndustryBaseInfo,
    IndustryConstituent,
    IndustryDaily,
    IndustryWeight,
    Interval,
    KlineBar,
    SecurityType,
    SecurityTypeFuture,
    SecurityTypeOption,
    StockBasic,
    StockInfo,
)


class TestInterval:
    """Interval 枚举测试."""

    def test_from_value_string(self):
        """从字符串值创建 Interval."""
        assert Interval.from_value("day") == Interval.DAY
        assert Interval.from_value("week") == Interval.WEEK
        assert Interval.from_value("month") == Interval.MONTH
        assert Interval.from_value("min1") == Interval.MIN1

    def test_from_value_int(self):
        """从整数值创建 Interval（注意：from_value 使用枚举字符串值，不是 SDK 值）."""
        # from_value 接受的是枚举的 value 字符串，不是 SDK period 值
        # 这里测试传入整数时会被转为字符串查找
        with pytest.raises(ValueError):
            Interval.from_value(10008)  # 10008 不是有效的枚举 value

    def test_from_sdk_period_value(self):
        """从 SDK Period 值创建 Interval."""
        assert Interval.from_sdk_period_value(10008) == Interval.DAY
        assert Interval.from_sdk_period_value(10009) == Interval.WEEK
        assert Interval.from_sdk_period_value(10012) == Interval.YEAR

    def test_to_sdk_period_value(self):
        """转换为 SDK Period 值."""
        assert Interval.DAY.to_sdk_period_value() == 10008
        assert Interval.WEEK.to_sdk_period_value() == 10009
        assert Interval.YEAR.to_sdk_period_value() == 10012

    def test_from_period_name(self):
        """从周期名称创建 Interval."""
        assert Interval.from_period_name("day") == Interval.DAY
        assert Interval.from_period_name("week") == Interval.WEEK
        assert Interval.from_period_name("min1") == Interval.MIN1

    def test_to_period_name(self):
        """获取周期名称."""
        assert Interval.DAY.to_period_name() == "day"
        assert Interval.WEEK.to_period_name() == "week"
        assert Interval.YEAR.to_period_name() == "year"

    def test_invalid_value_raises(self):
        """无效值应抛出 ValueError."""
        with pytest.raises(ValueError):
            Interval.from_value("invalid")
        with pytest.raises(ValueError):
            Interval.from_sdk_period_value(99999)

    def test_all_intervals_exist(self):
        """所有 13 种周期都应存在."""
        assert len(Interval) == 13
        assert Interval.MIN1.value == "min1"
        assert Interval.YEAR.value == "year"


class TestSecurityType:
    """SecurityType 枚举测试."""

    def test_extra_etf(self):
        """EXTRA_ETF 应存在."""
        assert SecurityType("EXTRA_ETF") == SecurityType.EXTRA_ETF

    def test_sh_a(self):
        """SH_A 应存在."""
        assert SecurityType("SH_A") == SecurityType.SH_A

    def test_all_security_types(self):
        """所有 SecurityType 值都应可访问."""
        assert SecurityType.EXTRA_STOCK_A.value == "EXTRA_STOCK_A"
        assert SecurityType.SH_ETF.value == "SH_ETF"
        assert SecurityType.SZ_ETF.value == "SZ_ETF"


class TestSecurityTypeFuture:
    """SecurityTypeFuture 枚举测试."""

    def test_extra_future(self):
        """EXTRA_FUTURE 应存在."""
        assert SecurityTypeFuture("EXTRA_FUTURE") == SecurityTypeFuture.EXTRA_FUTURE

    def test_zj_future(self):
        """ZJ_FUTURE 应存在."""
        assert SecurityTypeFuture("ZJ_FUTURE") == SecurityTypeFuture.ZJ_FUTURE


class TestSecurityTypeOption:
    """SecurityTypeOption 枚举测试."""

    def test_extra_etf_op(self):
        """EXTRA_ETF_OP 应存在."""
        assert SecurityTypeOption("EXTRA_ETF_OP") == SecurityTypeOption.EXTRA_ETF_OP

    def test_sh_option(self):
        """SH_OPTION 应存在."""
        assert SecurityTypeOption("SH_OPTION") == SecurityTypeOption.SH_OPTION


class TestKlineBar:
    """KlineBar dataclass 测试."""

    def test_construction(self):
        """KlineBar 可用所有字段构造."""
        bar = KlineBar(
            symbol="600000.SH",
            trade_time=datetime(2024, 1, 15, 10, 30),
            open=10.5,
            high=11.0,
            low=10.2,
            close=10.8,
            volume=100000,
            amount=1080000.0,
            security_type=SecurityType.SH_A,
        )
        assert bar.symbol == "600000.SH"
        assert bar.open == 10.5
        assert bar.security_type == SecurityType.SH_A

    def test_none_fields(self):
        """KlineBar 的 OHLCV 字段可为 None."""
        bar = KlineBar(
            symbol="510050.SH",
            trade_time=datetime(2024, 1, 15),
            open=None,
            high=None,
            low=None,
            close=None,
            volume=None,
            amount=None,
            security_type=SecurityType.SH_ETF,
        )
        assert bar.open is None
        assert bar.volume is None

    def test_equality(self):
        """两个相同字段的 KlineBar 应相等."""
        kwargs = {
            "symbol": "600000.SH",
            "trade_time": datetime(2024, 1, 15),
            "open": 10.5,
            "high": 11.0,
            "low": 10.2,
            "close": 10.8,
            "volume": 100000,
            "amount": 1080000.0,
            "security_type": SecurityType.SH_A,
        }
        assert KlineBar(**kwargs) == KlineBar(**kwargs)

    def test_inequality(self):
        """不同字段的 KlineBar 不应相等."""
        base = {
            "symbol": "600000.SH",
            "trade_time": datetime(2024, 1, 15),
            "open": 10.5,
            "high": 11.0,
            "low": 10.2,
            "close": 10.8,
            "volume": 100000,
            "amount": 1080000.0,
            "security_type": SecurityType.SH_A,
        }
        other = {**base, "symbol": "000001.SZ"}
        assert KlineBar(**base) != KlineBar(**other)


class TestStockInfo:
    """StockInfo dataclass 测试."""

    def test_construction(self):
        """StockInfo 可用 symbol 和 list_date 构造."""
        info = StockInfo(symbol="600000.SH", list_date="19991110")
        assert info.symbol == "600000.SH"
        assert info.list_date == "19991110"

    def test_none_list_date(self):
        """StockInfo 的 list_date 可为 None."""
        info = StockInfo(symbol="600000.SH", list_date=None)
        assert info.list_date is None

    def test_equality(self):
        """相同字段的 StockInfo 应相等."""
        assert StockInfo("600000.SH", "19991110") == StockInfo("600000.SH", "19991110")


class TestStockBasic:
    """StockBasic dataclass 测试."""

    def test_construction(self):
        """StockBasic 可用所有字段构造."""
        basic = StockBasic(
            symbol="600000.SH",
            security_type=SecurityType.SH_A,
            list_date="19991110",
            delist_date=None,
            stock_name="浦发银行",
            market="SH",
            exchange="SSE",
        )
        assert basic.symbol == "600000.SH"
        assert basic.stock_name == "浦发银行"
        assert basic.security_type == SecurityType.SH_A

    def test_equality(self):
        """相同字段的 StockBasic 应相等."""
        kwargs = {
            "symbol": "600000.SH",
            "security_type": SecurityType.SH_A,
            "list_date": "19991110",
            "delist_date": None,
            "stock_name": "浦发银行",
            "market": "SH",
            "exchange": "SSE",
        }
        assert StockBasic(**kwargs) == StockBasic(**kwargs)


class TestBackwardFactor:
    """BackwardFactor dataclass 测试."""

    def test_construction(self):
        """BackwardFactor 可用所有字段构造."""
        factor = BackwardFactor(
            symbol="600000.SH",
            trade_time=date(2024, 1, 15),
            backward_factor=1.05,
        )
        assert factor.symbol == "600000.SH"
        assert factor.backward_factor == 1.05

    def test_equality(self):
        """相同字段的 BackwardFactor 应相等."""
        kwargs = {
            "symbol": "600000.SH",
            "trade_time": date(2024, 1, 15),
            "backward_factor": 1.05,
        }
        assert BackwardFactor(**kwargs) == BackwardFactor(**kwargs)

    def test_inequality(self):
        """不同 factor 值不应相等."""
        a = BackwardFactor("600000.SH", date(2024, 1, 15), 1.05)
        b = BackwardFactor("600000.SH", date(2024, 1, 15), 1.10)
        assert a != b


# =====================================================================
# 指数数据值对象（交易所指数 + 行业指数）
# =====================================================================


class TestIndexConstituent:
    """IndexConstituent（交易所指数成分股）dataclass 测试."""

    def test_construction(self):
        """IndexConstituent 可用所有字段构造."""
        c = IndexConstituent(
            index_code="000300.SH",
            con_code="600000.SH",
            in_date="20240101",
            out_date=None,
            index_name="沪深300",
        )
        assert c.index_code == "000300.SH"
        assert c.con_code == "600000.SH"
        assert c.in_date == "20240101"
        assert c.out_date is None
        assert c.index_name == "沪深300"

    def test_none_fields(self):
        """out_date / index_name / in_date 可为 None."""
        c = IndexConstituent(
            index_code="000300.SH",
            con_code="600000.SH",
            in_date=None,
            out_date=None,
            index_name=None,
        )
        assert c.in_date is None
        assert c.out_date is None
        assert c.index_name is None

    def test_equality(self):
        """相同字段应相等."""
        kwargs = {
            "index_code": "000300.SH",
            "con_code": "600000.SH",
            "in_date": "20240101",
            "out_date": None,
            "index_name": "沪深300",
        }
        assert IndexConstituent(**kwargs) == IndexConstituent(**kwargs)

    def test_inequality(self):
        """不同 con_code 不应相等."""
        a = IndexConstituent("000300.SH", "600000.SH", "20240101", None, None)
        b = IndexConstituent("000300.SH", "000001.SZ", "20240101", None, None)
        assert a != b


class TestIndexWeight:
    """IndexWeight（交易所指数日权重）dataclass 测试."""

    def test_construction(self):
        """IndexWeight 可用所有字段构造."""
        w = IndexWeight(
            index_code="000300.SH",
            con_code="600000.SH",
            trade_date="20240115",
            total_share=1e9,
            free_share_ratio=80.0,
            calc_share=8e8,
            weight_factor=1.0,
            weight=2.5,
            close=10.5,
        )
        assert w.index_code == "000300.SH"
        assert w.trade_date == "20240115"
        assert w.weight == 2.5
        assert w.close == 10.5

    def test_none_fields(self):
        """所有数值字段可为 None（仅 PK 字段必填）."""
        w = IndexWeight(
            index_code="000300.SH",
            con_code="600000.SH",
            trade_date="20240115",
            total_share=None,
            free_share_ratio=None,
            calc_share=None,
            weight_factor=None,
            weight=None,
            close=None,
        )
        assert w.total_share is None
        assert w.weight is None
        assert w.close is None

    def test_equality(self):
        """相同字段应相等."""
        kwargs = {
            "index_code": "000300.SH",
            "con_code": "600000.SH",
            "trade_date": "20240115",
            "total_share": 1e9,
            "free_share_ratio": 80.0,
            "calc_share": 8e8,
            "weight_factor": 1.0,
            "weight": 2.5,
            "close": 10.5,
        }
        assert IndexWeight(**kwargs) == IndexWeight(**kwargs)

    def test_inequality(self):
        """不同 trade_date 不应相等."""
        a = IndexWeight("000300.SH", "600000.SH", "20240115", None, None, None, None, None, None)
        b = IndexWeight("000300.SH", "600000.SH", "20240116", None, None, None, None, None, None)
        assert a != b


class TestIndustryBaseInfo:
    """IndustryBaseInfo（行业指数基本信息）dataclass 测试."""

    def test_construction(self):
        """IndustryBaseInfo 可用所有字段构造."""
        info = IndustryBaseInfo(
            index_code="801010.SI",
            industry_code="CSI28",
            level_type=1,
            level1_name="农林牧渔",
            level2_name=None,
            level3_name=None,
            is_pub=1,
            change_reason=None,
        )
        assert info.index_code == "801010.SI"
        assert info.industry_code == "CSI28"
        assert info.level_type == 1
        assert info.level1_name == "农林牧渔"

    def test_none_fields(self):
        """非 PK 字段可为 None."""
        info = IndustryBaseInfo(
            index_code="801010.SI",
            industry_code="CSI28",
            level_type=None,
            level1_name=None,
            level2_name=None,
            level3_name=None,
            is_pub=None,
            change_reason=None,
        )
        assert info.level_type is None
        assert info.is_pub is None

    def test_equality(self):
        """相同字段应相等."""
        kwargs = {
            "index_code": "801010.SI",
            "industry_code": "CSI28",
            "level_type": 1,
            "level1_name": "农林牧渔",
            "level2_name": None,
            "level3_name": None,
            "is_pub": 1,
            "change_reason": None,
        }
        assert IndustryBaseInfo(**kwargs) == IndustryBaseInfo(**kwargs)

    def test_inequality(self):
        """不同 industry_code 不应相等."""
        a = IndustryBaseInfo("801010.SI", "CSI28", None, None, None, None, None, None)
        b = IndustryBaseInfo("801010.SI", "CSI99", None, None, None, None, None, None)
        assert a != b


class TestIndustryConstituent:
    """IndustryConstituent（行业指数成分股）dataclass 测试."""

    def test_construction(self):
        """IndustryConstituent 可用所有字段构造."""
        c = IndustryConstituent(
            index_code="801010.SI",
            con_code="600000.SH",
            in_date="20240101",
            out_date=None,
            index_name="农林牧渔",
        )
        assert c.index_code == "801010.SI"
        assert c.in_date == "20240101"

    def test_none_fields(self):
        """in_date/out_date/index_name 可为 None."""
        c = IndustryConstituent(
            index_code="801010.SI",
            con_code="600000.SH",
            in_date=None,
            out_date=None,
            index_name=None,
        )
        assert c.in_date is None
        assert c.out_date is None
        assert c.index_name is None

    def test_equality(self):
        """相同字段应相等."""
        kwargs = {
            "index_code": "801010.SI",
            "con_code": "600000.SH",
            "in_date": "20240101",
            "out_date": None,
            "index_name": "农林牧渔",
        }
        assert IndustryConstituent(**kwargs) == IndustryConstituent(**kwargs)

    def test_inequality(self):
        """不同 index_code 不应相等."""
        a = IndustryConstituent("801010.SI", "600000.SH", "20240101", None, None)
        b = IndustryConstituent("801020.SI", "600000.SH", "20240101", None, None)
        assert a != b


class TestIndustryWeight:
    """IndustryWeight（行业指数日权重）dataclass 测试."""

    def test_construction(self):
        """IndustryWeight 可用所有字段构造."""
        w = IndustryWeight(
            index_code="801010.SI",
            con_code="600000.SH",
            trade_date="20240115",
            weight=3.2,
        )
        assert w.index_code == "801010.SI"
        assert w.trade_date == "20240115"
        assert w.weight == 3.2

    def test_none_weight(self):
        """weight 可为 None."""
        w = IndustryWeight("801010.SI", "600000.SH", "20240115", None)
        assert w.weight is None

    def test_equality(self):
        """相同字段应相等."""
        kwargs = {
            "index_code": "801010.SI",
            "con_code": "600000.SH",
            "trade_date": "20240115",
            "weight": 3.2,
        }
        assert IndustryWeight(**kwargs) == IndustryWeight(**kwargs)

    def test_inequality(self):
        """不同 weight 不应相等."""
        a = IndustryWeight("801010.SI", "600000.SH", "20240115", 3.2)
        b = IndustryWeight("801010.SI", "600000.SH", "20240115", 3.5)
        assert a != b


class TestIndustryDaily:
    """IndustryDaily（行业指数日行情）dataclass 测试."""

    def test_construction(self):
        """IndustryDaily 可用所有字段构造（含 PB/PE/市值）."""
        d = IndustryDaily(
            index_code="801010.SI",
            trade_date="20240115",
            open=1000.0,
            high=1010.0,
            low=995.0,
            close=1005.0,
            pre_close=1000.0,
            volume=1e8,
            amount=1e10,
            pb=2.5,
            pe=15.0,
            total_cap=5e6,
            a_float_cap=4e6,
        )
        assert d.index_code == "801010.SI"
        assert d.trade_date == "20240115"
        assert d.pb == 2.5
        assert d.pe == 15.0
        assert d.total_cap == 5e6

    def test_none_fields(self):
        """OHLCV/估值字段可为 None（仅 PK 必填）."""
        d = IndustryDaily(
            index_code="801010.SI",
            trade_date="20240115",
            open=None,
            high=None,
            low=None,
            close=None,
            pre_close=None,
            volume=None,
            amount=None,
            pb=None,
            pe=None,
            total_cap=None,
            a_float_cap=None,
        )
        assert d.open is None
        assert d.pb is None
        assert d.a_float_cap is None

    def test_equality(self):
        """相同字段应相等."""
        kwargs = {
            "index_code": "801010.SI",
            "trade_date": "20240115",
            "open": 1000.0,
            "high": 1010.0,
            "low": 995.0,
            "close": 1005.0,
            "pre_close": 1000.0,
            "volume": 1e8,
            "amount": 1e10,
            "pb": 2.5,
            "pe": 15.0,
            "total_cap": 5e6,
            "a_float_cap": 4e6,
        }
        assert IndustryDaily(**kwargs) == IndustryDaily(**kwargs)

    def test_inequality(self):
        """不同 close 不应相等."""
        base = {
            "index_code": "801010.SI",
            "trade_date": "20240115",
            "open": None,
            "high": None,
            "low": None,
            "close": 1005.0,
            "pre_close": None,
            "volume": None,
            "amount": None,
            "pb": None,
            "pe": None,
            "total_cap": None,
            "a_float_cap": None,
        }
        other = {**base, "close": 1006.0}
        assert IndustryDaily(**base) != IndustryDaily(**other)
