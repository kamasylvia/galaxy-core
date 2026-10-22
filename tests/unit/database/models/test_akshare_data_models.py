"""akshare 资金流向 DB model 单元测试(nocodb 形态,2026-08-26 回迁).

表名=中文;PK=业务复合键;性能索引在 DB 层(P3 补建),ORM 不声明;
trade_date=Date;系统列为 naive DateTime。不触数据库。
"""

from datetime import date as date_type

import pytest
from sqlalchemy import DateTime, Index, PrimaryKeyConstraint, String

from galaxy_core.database.models.akshare_data import AkshareSectorFundFlowDaily


def _columns(model_cls) -> dict:
    return {c.name: c for c in model_cls.__table__.columns}


def _is_timestamptz(col) -> bool:
    return isinstance(col.type, DateTime) and col.type.timezone


def _pk_col_names(model_cls) -> list[str]:
    pk_constraints = [
        c for c in model_cls.__table__.constraints if isinstance(c, PrimaryKeyConstraint)
    ]
    if not pk_constraints:
        return []
    return [c.name for c in pk_constraints[0].columns]


def _index_names(model_cls) -> list[str]:
    return [idx.name for idx in model_cls.__table__.indexes if isinstance(idx, Index)]


class TestAkshareSectorFundFlowDailyModel:
    def test_tablename(self):
        assert AkshareSectorFundFlowDaily.__tablename__ == "akshare_sector_fund_flow_daily"

    def test_primary_key(self):
        assert _pk_col_names(AkshareSectorFundFlowDaily) == [
            "trade_date", "sector_type", "sector_name"
        ]

    def test_no_orm_declared_indexes(self):
        """性能索引由 DB 层 P3 补建,ORM 不声明索引."""
        assert _index_names(AkshareSectorFundFlowDaily) == []

    def test_trade_date_is_date(self):
        from sqlalchemy import Date

        assert isinstance(_columns(AkshareSectorFundFlowDaily)["trade_date"].type, Date)

    def test_trade_date_is_not_string(self):
        assert not isinstance(
            _columns(AkshareSectorFundFlowDaily)["trade_date"].type, String
        )

    def test_repr_does_not_raise(self):
        obj = AkshareSectorFundFlowDaily(
            trade_date=date_type(2024, 1, 15),
            sector_type="行业资金流",
            sector_name="银行",
        )
        assert "银行" in repr(obj)


class TestAkshareTimestampColumns:
    """NocoDB 系统时间列为 naive DateTime(应用不写)."""

    @pytest.mark.parametrize(
        "model_cls",
        [AkshareSectorFundFlowDaily],
    )
    def test_has_naive_system_timestamps(self, model_cls):
        cols = _columns(model_cls)
        assert "created_at" in cols
        assert "updated_at" in cols
        for c in ("created_at", "updated_at"):
            assert isinstance(cols[c].type, DateTime)
            assert not cols[c].type.timezone
        assert "id" in cols
