"""指数数据 DB model 单元测试(nocodb 形态,2026-08-26 回迁).

验证 index_data.py 中 6 个 ORM model 的表结构元数据：
- __tablename__ 为 nocodb 中文表名
- 主键列（PrimaryKeyConstraint）正确(业务复合键)
- 性能索引由 DB 层 P3 补建,ORM 不声明
- __repr__ 不抛异常
- trade_date / in_date 为 Date 类型

不触数据库，纯元数据反射检查。
"""

from datetime import date as date_type

import pytest
from sqlalchemy import Date, DateTime, Index, PrimaryKeyConstraint, String

from galaxy_core.database.models.index_data import (
    IndexConstituent,
    IndexWeight,
    IndustryBaseInfo,
    IndustryConstituent,
    IndustryDaily,
    IndustryWeight,
)


def _columns(model_cls) -> dict:
    """返回 {列名: Column} 映射."""
    return {c.name: c for c in model_cls.__table__.columns}


def _pk_col_names(model_cls) -> list[str]:
    """返回主键列名列表."""
    pk_constraints = [
        c for c in model_cls.__table__.constraints if isinstance(c, PrimaryKeyConstraint)
    ]
    if not pk_constraints:
        return []
    return [c.name for c in pk_constraints[0].columns]


def _index_names(model_cls) -> list[str]:
    """返回二级索引名列表."""
    return [idx.name for idx in model_cls.__table__.indexes if isinstance(idx, Index)]


class TestIndexConstituentModel:
    """IndexConstituent model 测试."""

    def test_tablename(self):
        assert IndexConstituent.__tablename__ == "index_constituent"

    def test_primary_key(self):
        assert _pk_col_names(IndexConstituent) == [
            "index_code",
            "con_code",
            "in_date",
        ]

    def test_no_orm_declared_indexes(self):
        """性能索引由 DB 层 P3 补建,ORM 不声明索引."""
        assert _index_names(IndexConstituent) == []

    def test_repr_does_not_raise(self):
        """__repr__ 应可执行不抛异常."""
        obj = IndexConstituent(
            index_code="000300.SH",
            con_code="600000.SH",
            in_date="20240101",
        )
        repr_str = repr(obj)
        assert "000300.SH" in repr_str


class TestIndexWeightModel:
    """IndexWeight model 测试."""

    def test_tablename(self):
        assert IndexWeight.__tablename__ == "index_weight"

    def test_primary_key(self):
        assert _pk_col_names(IndexWeight) == [
            "index_code",
            "con_code",
            "trade_date",
        ]

    def test_no_orm_declared_indexes(self):
        """性能索引由 DB 层 P3 补建,ORM 不声明索引."""
        assert _index_names(IndexWeight) == []

    def test_repr_does_not_raise(self):
        obj = IndexWeight(
            index_code="000300.SH",
            con_code="600000.SH",
            trade_date="20240115",
        )
        assert "000300.SH" in repr(obj)


class TestIndustryBaseInfoModel:
    """IndustryBaseInfo model 测试."""

    def test_tablename(self):
        assert IndustryBaseInfo.__tablename__ == "industry_base_info"

    def test_primary_key(self):
        assert _pk_col_names(IndustryBaseInfo) == ["index_code", "industry_code"]

    def test_no_orm_declared_indexes(self):
        """性能索引由 DB 层 P3 补建,ORM 不声明索引."""
        assert _index_names(IndustryBaseInfo) == []

    def test_repr_does_not_raise(self):
        obj = IndustryBaseInfo(index_code="801010.SI", industry_code="CSI28")
        assert "801010.SI" in repr(obj)


class TestIndustryConstituentModel:
    """IndustryConstituent model 测试."""

    def test_tablename(self):
        assert IndustryConstituent.__tablename__ == "industry_constituent"

    def test_primary_key(self):
        assert _pk_col_names(IndustryConstituent) == [
            "index_code",
            "con_code",
            "in_date",
        ]

    def test_no_orm_declared_indexes(self):
        """性能索引由 DB 层 P3 补建,ORM 不声明索引."""
        assert _index_names(IndustryConstituent) == []

    def test_repr_does_not_raise(self):
        obj = IndustryConstituent(
            index_code="801010.SI",
            con_code="600000.SH",
            in_date="20240101",
        )
        assert "801010.SI" in repr(obj)


class TestIndustryWeightModel:
    """IndustryWeight model 测试."""

    def test_tablename(self):
        assert IndustryWeight.__tablename__ == "industry_weight"

    def test_primary_key(self):
        assert _pk_col_names(IndustryWeight) == [
            "index_code",
            "con_code",
            "trade_date",
        ]

    def test_no_orm_declared_indexes(self):
        """性能索引由 DB 层 P3 补建,ORM 不声明索引."""
        assert _index_names(IndustryWeight) == []

    def test_repr_does_not_raise(self):
        obj = IndustryWeight(
            index_code="801010.SI",
            con_code="600000.SH",
            trade_date="20240115",
        )
        assert "801010.SI" in repr(obj)


class TestIndustryDailyModel:
    """IndustryDaily model 测试（hypertable，trade_date 为 Date 类型）."""

    def test_tablename(self):
        assert IndustryDaily.__tablename__ == "industry_daily"

    def test_primary_key(self):
        assert _pk_col_names(IndustryDaily) == ["index_code", "trade_date"]

    def test_no_orm_declared_indexes(self):
        """性能索引由 DB 层 P3 补建,ORM 不声明索引."""
        assert _index_names(IndustryDaily) == []

    def test_trade_date_is_date(self):
        """nocodb 形态:trade_date 为 Date(北京日期)."""
        cols = _columns(IndustryDaily)
        assert isinstance(cols["trade_date"].type, Date)

    def test_trade_date_is_not_string(self):
        """trade_date 不应为 String（区别于其他表的 YYYYMMDD 字符串）."""
        cols = _columns(IndustryDaily)
        assert not isinstance(cols["trade_date"].type, String)

    def test_has_estimation_fields(self):
        """应包含 PB/PE/市值估值字段."""
        cols = _columns(IndustryDaily)
        for field in ("pb", "pe", "total_cap", "a_float_cap"):
            assert field in cols

    def test_repr_does_not_raise(self):
        obj = IndustryDaily(index_code="801010.SI", trade_date=date_type(2024, 1, 15))
        assert "801010.SI" in repr(obj)


class TestTimestampColumns:
    """NocoDB 系统时间列为 naive DateTime(应用不写,无 default/onupdate)."""

    @pytest.mark.parametrize(
        "model_cls",
        [
            IndexConstituent,
            IndexWeight,
            IndustryBaseInfo,
            IndustryConstituent,
            IndustryWeight,
            IndustryDaily,
        ],
    )
    def test_has_audit_timestamps(self, model_cls):
        cols = _columns(model_cls)
        assert "created_at" in cols
        assert "updated_at" in cols
        for c in ("created_at", "updated_at"):
            assert isinstance(cols[c].type, DateTime)
            assert not cols[c].type.timezone
        assert "id" in cols

    def test_system_columns_have_no_defaults(self):
        """NocoDB 系统列无 default/onupdate(应用不写,由 NocoDB/DB 侧管理)."""
        cols = _columns(IndexConstituent)
        assert cols["created_at"].default is None
        assert cols["updated_at"].onupdate is None
