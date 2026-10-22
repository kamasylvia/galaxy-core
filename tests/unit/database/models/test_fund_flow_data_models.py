"""AmazingData 资金流向 DB model 单元测试(nocodb 形态,2026-08-26 回迁).

4 个 model 元数据反射(tablename 中文 / PK / trade_date Date / repr),不触数据库。
性能索引由 DB 层 P3 补建,ORM 不声明;系统列为 naive DateTime。
"""

from datetime import date as date_type

import pytest
from sqlalchemy import DateTime, Index, PrimaryKeyConstraint, String

from galaxy_core.database.models.fund_flow_data import (
    BlockTrading,
    LongHuBang,
    MarginDetailDaily,
    MarginSummaryDaily,
)


def _columns(model_cls) -> dict:
    return {c.name: c for c in model_cls.__table__.columns}


def _is_timestamptz(col) -> bool:
    """判断列是否是 DateTime(timezone=True)."""
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


class TestLongHuBangModel:
    def test_tablename(self):
        assert LongHuBang.__tablename__ == "long_hu_bang"

    def test_primary_key(self):
        assert _pk_col_names(LongHuBang) == [
            "market_code", "trade_date", "trader_name", "flow_mark"
        ]

    def test_no_orm_declared_indexes(self):
        """性能索引由 DB 层 P3 补建,ORM 不声明索引."""
        assert _index_names(LongHuBang) == []

    def test_trade_date_is_date(self):
        """nocodb 形态:trade_date 为 Date(北京日期)."""
        from sqlalchemy import Date

        assert isinstance(_columns(LongHuBang)["trade_date"].type, Date)

    def test_trade_date_is_not_string(self):
        assert not isinstance(_columns(LongHuBang)["trade_date"].type, String)

    def test_flow_mark_is_int_pk(self):
        """关键:flow_mark 是 int PK(1=买/2=卖,非 str)."""
        col = _columns(LongHuBang)["flow_mark"]
        assert col.primary_key

    def test_repr_does_not_raise(self):
        obj = LongHuBang(
            market_code="600000.SH",
            trade_date=date_type(2024, 1, 15),
            trader_name="某席位",
            flow_mark=1,
        )
        assert "600000.SH" in repr(obj)


class TestBlockTradingModel:
    def test_tablename(self):
        assert BlockTrading.__tablename__ == "block_trading"

    def test_primary_key(self):
        assert _pk_col_names(BlockTrading) == [
            "market_code", "trade_date", "b_buyer_name", "b_seller_name"
        ]

    def test_no_orm_declared_indexes(self):
        """性能索引由 DB 层 P3 补建,ORM 不声明索引."""
        assert _index_names(BlockTrading) == []

    def test_trade_date_is_date(self):
        from sqlalchemy import Date

        assert isinstance(_columns(BlockTrading)["trade_date"].type, Date)

    def test_trade_date_is_not_string(self):
        assert not isinstance(_columns(BlockTrading)["trade_date"].type, String)

    def test_repr_does_not_raise(self):
        obj = BlockTrading(
            market_code="600000.SH",
            trade_date=date_type(2024, 1, 15),
            b_buyer_name="买方",
            b_seller_name="卖方",
        )
        assert "600000.SH" in repr(obj)


class TestMarginSummaryDailyModel:
    def test_tablename(self):
        assert MarginSummaryDaily.__tablename__ == "margin_summary_daily"

    def test_primary_key(self):
        assert _pk_col_names(MarginSummaryDaily) == ["trade_date"]

    def test_no_orm_declared_indexes(self):
        """性能索引由 DB 层 P3 补建,ORM 不声明索引."""
        assert _index_names(MarginSummaryDaily) == []

    def test_trade_date_is_date(self):
        from sqlalchemy import Date

        assert isinstance(_columns(MarginSummaryDaily)["trade_date"].type, Date)

    def test_trade_date_is_not_string(self):
        assert not isinstance(_columns(MarginSummaryDaily)["trade_date"].type, String)

    def test_repr_does_not_raise(self):
        obj = MarginSummaryDaily(trade_date=date_type(2024, 1, 15))
        assert "2024" in repr(obj)


class TestMarginDetailDailyModel:
    def test_tablename(self):
        assert MarginDetailDaily.__tablename__ == "margin_detail_daily"

    def test_primary_key(self):
        assert _pk_col_names(MarginDetailDaily) == ["market_code", "trade_date"]

    def test_no_orm_declared_indexes(self):
        """性能索引由 DB 层 P3 补建,ORM 不声明索引."""
        assert _index_names(MarginDetailDaily) == []

    def test_trade_date_is_date(self):
        from sqlalchemy import Date

        assert isinstance(_columns(MarginDetailDaily)["trade_date"].type, Date)

    def test_trade_date_is_not_string(self):
        assert not isinstance(_columns(MarginDetailDaily)["trade_date"].type, String)

    def test_repr_does_not_raise(self):
        obj = MarginDetailDaily(
            market_code="600000.SH", trade_date=date_type(2024, 1, 15)
        )
        assert "600000.SH" in repr(obj)


class TestFundFlowTimestampColumns:
    """NocoDB 系统时间列为 naive DateTime(应用不写)."""

    @pytest.mark.parametrize(
        "model_cls",
        [LongHuBang, BlockTrading, MarginSummaryDaily, MarginDetailDaily],
    )
    def test_has_naive_system_timestamps(self, model_cls):
        cols = _columns(model_cls)
        assert "created_at" in cols
        assert "updated_at" in cols
        for c in ("created_at", "updated_at"):
            assert isinstance(cols[c].type, DateTime)
            assert not cols[c].type.timezone
        assert "id" in cols
