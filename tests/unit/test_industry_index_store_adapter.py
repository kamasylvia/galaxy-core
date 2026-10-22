"""IndustryIndexStoreAdapter 测试.

验证 adapter 满足 IndustryIndexStorePort Protocol，并能正确 UPSERT
IndustryBaseInfo / IndustryConstituent / IndustryWeight / IndustryDaily 值对象。
IndustryDaily 的 trade_date 需从 YYYYMMDD 字符串转 Date 对象（hypertable 要求）。
所有 DB 操作经 mock AsyncDatabaseManager，不触真实数据库。
"""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from galaxy_core.database.services.adapters.industry_index_store_adapter import (
    IndustryIndexStoreAdapter,
    _yyyymmdd_to_date,
)
from galaxy_core.domain.ports.industry_index_store import IndustryIndexStorePort
from galaxy_core.domain.value_objects import (
    IndustryBaseInfo,
    IndustryConstituent,
    IndustryDaily,
    IndustryWeight,
)
from galaxy_core.shared_kernel.exceptions import CacheError


def _make_mock_db() -> tuple[MagicMock, AsyncMock]:
    """构造 mock AsyncDatabaseManager 与可复用的 session ctx."""
    mock_session = AsyncMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_db = MagicMock()
    mock_db.session.return_value = mock_session_ctx
    return mock_db, mock_session


class TestYyyyMMddToDate:
    """_yyyymmdd_to_date 辅助函数测试(IndustryDaily.trade_date 转换核心).

    2026-08-26 nocodb 回迁:trade_date 列为 date,返回 date 对象。
    """

    def test_valid_date(self):
        """合法 YYYYMMDD 字符串应转为 date(北京日期)."""
        from datetime import date as date_type

        result = _yyyymmdd_to_date("20240115")
        assert result == date_type(2024, 1, 15)

    def test_none_returns_none(self):
        """None 输入应返回 None."""
        assert _yyyymmdd_to_date(None) is None

    def test_invalid_returns_none(self):
        """非法字符串应返回 None（不抛异常）."""
        assert _yyyymmdd_to_date("not-a-date") is None
        assert _yyyymmdd_to_date("2024") is None
        assert _yyyymmdd_to_date("20241301") is None  # 非法月份


class TestIndustryIndexStoreAdapterProtocol:
    """验证 IndustryIndexStoreAdapter 满足 IndustryIndexStorePort Protocol."""

    def test_adapter_is_protocol_instance(self):
        """IndustryIndexStoreAdapter 应满足 IndustryIndexStorePort Protocol."""
        mock_db = MagicMock()
        adapter = IndustryIndexStoreAdapter(mock_db)
        assert isinstance(adapter, IndustryIndexStorePort)

    def test_adapter_has_async_save_methods(self):
        """4 个 save_* 方法应均为 async."""
        import inspect

        mock_db = MagicMock()
        adapter = IndustryIndexStoreAdapter(mock_db)
        for method in (
            "save_industry_base_info",
            "save_industry_constituent",
            "save_industry_weight",
            "save_industry_daily",
        ):
            assert inspect.iscoroutinefunction(getattr(adapter, method))

    def test_adapter_has_async_query_methods(self):
        """查询/判空方法应均为 async."""
        import inspect

        mock_db = MagicMock()
        adapter = IndustryIndexStoreAdapter(mock_db)
        assert inspect.iscoroutinefunction(adapter.get_industry_daily_last_date)
        assert inspect.iscoroutinefunction(adapter.get_industry_daily_max_last_date)
        assert inspect.iscoroutinefunction(adapter.is_industry_base_info_empty)


class TestSaveIndustryBaseInfo:
    """save_industry_base_info 方法测试."""

    def test_empty_list_returns_zero_without_db(self):
        """空列表应直接返回 0，不操作数据库."""
        mock_db = MagicMock()
        adapter = IndustryIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.save_industry_base_info([]))
        assert result == 0
        mock_db.session.assert_not_called()

    def test_missing_pk_filtered_returns_zero(self):
        """缺 index_code 或 industry_code 的记录应被过滤."""
        mock_db = MagicMock()
        adapter = IndustryIndexStoreAdapter(mock_db)
        records = [
            IndustryBaseInfo(
                index_code=None,
                industry_code="CSI28",
                level_type=None,
                level1_name=None,
                level2_name=None,
                level3_name=None,
                is_pub=None,
                change_reason=None,
            )
        ]
        result = asyncio.run(adapter.save_industry_base_info(records))
        assert result == 0
        mock_db.session.assert_not_called()

    def test_saves_base_info_and_returns_count(self):
        """应 UPSERT 基本信息记录并返回写入条数."""
        mock_db, mock_session = _make_mock_db()
        adapter = IndustryIndexStoreAdapter(mock_db)
        records = [
            IndustryBaseInfo(
                index_code="801010.SI",
                industry_code="CSI28",
                level_type=1,
                level1_name="农林牧渔",
                level2_name=None,
                level3_name=None,
                is_pub=1,
                change_reason=None,
            )
        ]
        result = asyncio.run(adapter.save_industry_base_info(records))
        assert result == 1
        mock_db.session.assert_called_once()
        mock_session.execute.assert_called()


class TestSaveIndustryConstituent:
    """save_industry_constituent 方法测试."""

    def test_empty_list_returns_zero_without_db(self):
        """空列表应直接返回 0."""
        mock_db = MagicMock()
        adapter = IndustryIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.save_industry_constituent([]))
        assert result == 0
        mock_db.session.assert_not_called()

    def test_none_in_date_filtered_returns_zero(self):
        """in_date 为 None 的记录应被过滤."""
        mock_db = MagicMock()
        adapter = IndustryIndexStoreAdapter(mock_db)
        records = [
            IndustryConstituent("801010.SI", "600000.SH", None, None, None)
        ]
        result = asyncio.run(adapter.save_industry_constituent(records))
        assert result == 0
        mock_db.session.assert_not_called()

    def test_saves_constituents_and_returns_count(self):
        """应 UPSERT 成分股记录并返回写入条数."""
        mock_db, mock_session = _make_mock_db()
        adapter = IndustryIndexStoreAdapter(mock_db)
        records = [
            IndustryConstituent("801010.SI", "600000.SH", "20240101", None, "农林牧渔")
        ]
        result = asyncio.run(adapter.save_industry_constituent(records))
        assert result == 1
        mock_db.session.assert_called_once()


class TestSaveIndustryWeight:
    """save_industry_weight 方法测试."""

    def test_empty_list_returns_zero_without_db(self):
        """空列表应直接返回 0."""
        mock_db = MagicMock()
        adapter = IndustryIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.save_industry_weight([]))
        assert result == 0
        mock_db.session.assert_not_called()

    def test_none_trade_date_filtered_returns_zero(self):
        """trade_date 为 None 的记录应被过滤."""
        mock_db = MagicMock()
        adapter = IndustryIndexStoreAdapter(mock_db)
        records = [IndustryWeight("801010.SI", "600000.SH", None, None)]
        result = asyncio.run(adapter.save_industry_weight(records))
        assert result == 0
        mock_db.session.assert_not_called()

    def test_saves_weights_and_returns_count(self):
        """应 UPSERT 权重记录并返回写入条数."""
        mock_db, mock_session = _make_mock_db()
        adapter = IndustryIndexStoreAdapter(mock_db)
        records = [IndustryWeight("801010.SI", "600000.SH", "20240115", 3.2)]
        result = asyncio.run(adapter.save_industry_weight(records))
        assert result == 1
        mock_db.session.assert_called_once()


class TestSaveIndustryDaily:
    """save_industry_daily 方法测试（含 trade_date 字符串→Date 转换）."""

    def test_empty_list_returns_zero_without_db(self):
        """空列表应直接返回 0."""
        mock_db = MagicMock()
        adapter = IndustryIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.save_industry_daily([]))
        assert result == 0
        mock_db.session.assert_not_called()

    def test_invalid_trade_date_filtered_returns_zero(self):
        """trade_date 无法解析的记录应被过滤，全空则返回 0."""
        mock_db = MagicMock()
        adapter = IndustryIndexStoreAdapter(mock_db)
        records = [
            IndustryDaily(
                index_code="801010.SI",
                trade_date="not-a-date",
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
        ]
        result = asyncio.run(adapter.save_industry_daily(records))
        assert result == 0
        mock_db.session.assert_not_called()

    def test_saves_daily_and_returns_count(self):
        """应 UPSERT 日行情记录并返回写入条数."""
        mock_db, mock_session = _make_mock_db()
        adapter = IndustryIndexStoreAdapter(mock_db)
        records = [
            IndustryDaily(
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
        ]
        result = asyncio.run(adapter.save_industry_daily(records))
        assert result == 1
        mock_db.session.assert_called_once()


class TestGetIndustryDailyLastDate:
    """get_industry_daily_last_date 方法测试."""

    def test_returns_yyyymmdd_string(self):
        """有数据时应返回 YYYYMMDD 字符串."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar.return_value = date(2024, 1, 15)
        mock_session.execute.return_value = mock_result

        adapter = IndustryIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.get_industry_daily_last_date("801010.SI"))
        assert result == "20240115"

    def test_returns_none_when_no_data(self):
        """无数据（scalar None）应返回 None."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        adapter = IndustryIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.get_industry_daily_last_date("801010.SI"))
        assert result is None

    def test_returns_none_on_sqlalchemy_error(self):
        """SQLAlchemy 错误时应返回 None."""
        from sqlalchemy.exc import SQLAlchemyError

        mock_db, mock_session = _make_mock_db()
        mock_session.execute.side_effect = SQLAlchemyError("db down")

        adapter = IndustryIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.get_industry_daily_last_date("801010.SI"))
        assert result is None


class TestGetIndustryDailyMaxLastDate:
    """get_industry_daily_max_last_date 方法测试(2026-07-28 新增)。

    全局 MAX(trade_date) 查询,用于 _resolve_daily_range 统一窗口计算。
    """

    def test_returns_yyyymmdd_string(self):
        """有数据时应返回 YYYYMMDD 字符串."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar.return_value = date(2024, 1, 15)
        mock_session.execute.return_value = mock_result

        adapter = IndustryIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.get_industry_daily_max_last_date())
        assert result == "20240115"

    def test_returns_none_when_no_data(self):
        """无数据（scalar None）应返回 None."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        adapter = IndustryIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.get_industry_daily_max_last_date())
        assert result is None

    def test_returns_none_on_sqlalchemy_error(self):
        """SQLAlchemy 错误时应返回 None."""
        from sqlalchemy.exc import SQLAlchemyError

        mock_db, mock_session = _make_mock_db()
        mock_session.execute.side_effect = SQLAlchemyError("db down")

        adapter = IndustryIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.get_industry_daily_max_last_date())
        assert result is None


class TestIsIndustryBaseInfoEmpty:
    """is_industry_base_info_empty 方法测试."""

    def test_returns_true_when_count_zero(self):
        """表空（count=0）应返回 True."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_session.execute.return_value = mock_result

        adapter = IndustryIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.is_industry_base_info_empty())
        assert result is True

    def test_returns_false_when_count_positive(self):
        """表非空（count>0）应返回 False."""
        mock_db, mock_session = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 7
        mock_session.execute.return_value = mock_result

        adapter = IndustryIndexStoreAdapter(mock_db)
        result = asyncio.run(adapter.is_industry_base_info_empty())
        assert result is False


class TestUpsertErrorHandling:
    """UPSERT 异常应包装为 CacheError."""

    def test_base_info_upsert_raises_cache_error(self):
        """save_industry_base_info 遇 SQLAlchemyError 应抛 CacheError."""
        from sqlalchemy.exc import SQLAlchemyError

        mock_db, mock_session = _make_mock_db()
        mock_session.execute.side_effect = SQLAlchemyError("write failed")

        adapter = IndustryIndexStoreAdapter(mock_db)
        records = [
            IndustryBaseInfo(
                index_code="801010.SI",
                industry_code="CSI28",
                level_type=None,
                level1_name=None,
                level2_name=None,
                level3_name=None,
                is_pub=None,
                change_reason=None,
            )
        ]
        with pytest.raises(CacheError):
            asyncio.run(adapter.save_industry_base_info(records))
