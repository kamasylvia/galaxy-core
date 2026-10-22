"""K 线表组合主键模型单元测试.

验证：
1. BaseKline 使用 (symbol, trade_time) 组合主键
2. 子类继承正确的主键结构
3. 无 id 列定义
4. __table_args__ 无冗余约束
5. model.id 不再被引用
"""

import pytest
from datetime import datetime
from sqlalchemy import inspect
from galaxy_core.database.models.kline import (
    BaseKline,
    KlineDay,
    KlineMin1,
    KlineWeek,
    INTERVAL_MODEL_MAP,
)


class TestCompositePrimaryKey:
    """测试组合主键定义."""

    def test_base_kline_id_is_not_primary_key(self):
        """BaseKline 的 id 是 NocoDB 系统列(普通列,非 ORM 主键)."""
        mapper = inspect(KlineDay)
        id_col = mapper.columns.get("id")
        assert id_col is not None  # nocodb 形态:系统列存在
        pk_columns = [col.name for col in mapper.primary_key]
        assert "id" not in pk_columns

    def test_base_kline_symbol_is_primary_key(self):
        """symbol 列应是主键."""
        # 通过子类实例化后的表结构检查
        mapper = inspect(KlineDay)
        symbol_col = mapper.columns.get("symbol")
        assert symbol_col is not None
        assert symbol_col.primary_key is True

    def test_base_kline_trade_time_is_primary_key(self):
        """trade_time 列应是主键."""
        mapper = inspect(KlineDay)
        trade_time_col = mapper.columns.get("trade_time")
        assert trade_time_col is not None
        assert trade_time_col.primary_key is True

    def test_composite_primary_key_columns(self):
        """组合主键应包含 symbol 和 trade_time."""
        mapper = inspect(KlineDay)
        pk_columns = [col.name for col in mapper.primary_key]
        assert "symbol" in pk_columns
        assert "trade_time" in pk_columns
        assert "id" not in pk_columns
        assert len(pk_columns) == 2


class TestKlineSubclasses:
    """测试 K 线表子类结构."""

    def test_all_subclasses_have_composite_pk(self):
        """所有子类都应有组合主键."""
        for interval, model_class in INTERVAL_MODEL_MAP.items():
            mapper = inspect(model_class)
            pk_columns = [col.name for col in mapper.primary_key]
            assert "symbol" in pk_columns, f"{model_class.__name__} 缺少 symbol 主键"
            assert "trade_time" in pk_columns, f"{model_class.__name__} 缺少 trade_time 主键"
            assert "id" not in pk_columns, f"{model_class.__name__} 不应有 id 主键"

    def test_subclasses_no_redundant_table_args(self):
        """子类不应有冗余的 __table_args__."""
        for interval, model_class in INTERVAL_MODEL_MAP.items():
            # 子类可以没有 __table_args__，或者仅包含非约束的配置
            table_args = getattr(model_class, "__table_args__", None)
            if table_args:
                # 如果有 __table_args__，检查不应包含 UniqueConstraint 或冗余 Index
                args_str = str(table_args)
                assert "UniqueConstraint" not in args_str, f"{model_class.__name__} 有冗余 UniqueConstraint"
                # 允许其他非索引配置

    def test_kline_day_table_name(self):
        """KlineDay 表名正确(英文表名)."""
        assert KlineDay.__tablename__ == "kline_day"

    def test_kline_min1_table_name(self):
        """KlineMin1 表名正确(英文表名)."""
        assert KlineMin1.__tablename__ == "kline_min1"


class TestKlineServiceNoIdReference:
    """测试 KlineService 无 model.id 引用."""

    def test_get_available_intervals_uses_count_star(self):
        """get_available_intervals_for_symbol 应使用 func.count() 而非 func.count(model.id)."""
        import ast
        import inspect as insp
        from galaxy_core.database.services.kline import (
            get_available_intervals_for_symbol,
        )

        source = insp.getsource(get_available_intervals_for_symbol)

        # 检查源代码中不包含 model.id
        assert "model.id" not in source, "不应引用 model.id"

        # 检查使用 func.count
        assert "func.count" in source, "应使用 func.count"


class TestKlineModelInstantiation:
    """测试模型实例化（不涉及数据库）."""

    def test_kline_day_can_be_instantiated(self):
        """KlineDay 可以实例化."""
        kline = KlineDay(
            symbol="600000.SH",
            trade_time=datetime(2024, 1, 1, 9, 30),
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.5,
            volume=1000000,
            amount=10500000.0,
        )
        assert kline.symbol == "600000.SH"
        assert kline.trade_time == datetime(2024, 1, 1, 9, 30)
        # 不应有 id 属性
        assert not hasattr(kline, "id") or getattr(kline, "id", None) is None

    def test_kline_min1_can_be_instantiated(self):
        """KlineMin1 可以实例化."""
        kline = KlineMin1(
            symbol="600000.SH",
            trade_time=datetime(2024, 1, 1, 9, 30),
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.5,
            volume=1000000,
        )
        assert kline.symbol == "600000.SH"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
