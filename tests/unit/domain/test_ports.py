"""Domain 端口 Protocol 合规性测试.

验证 dummy 实现类通过 runtime_checkable Protocol 的 isinstance 检查。
"""

from datetime import date

import pandas as pd

from galaxy_core.domain.ports import (
    CalendarProviderPort,
    CalendarStorePort,
    ExchangeIndexProviderPort,
    ExchangeIndexStorePort,
    IndustryIndexProviderPort,
    IndustryIndexStorePort,
    KlineProviderPort,
    KlineStorePort,
    ReferenceProviderPort,
)
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
    StockBasic,
    StockInfo,
)

# =====================================================================
# Dummy 实现类 — 用于验证 Protocol 结构化子类型兼容性
# =====================================================================


class DummyKlineProvider:
    """KlineProviderPort 的 dummy 实现."""

    async def get_kline(
        self,
        symbols: list[str],
        interval: Interval,
        start: str,
        end: str,
    ) -> list[KlineBar]:
        return []

    async def get_stock_list(self, market: str) -> list[StockInfo]:
        return []

    async def get_listing_dates(self, symbols: list[str]) -> dict[str, date]:
        return {}


class DummyCalendarProvider:
    """CalendarProviderPort 的 dummy 实现."""

    async def get_trading_calendar(self, year: int) -> list[date]:
        return []


class DummyReferenceProvider:
    """ReferenceProviderPort 的 dummy 实现."""

    async def get_stock_basic(self, symbols: list[str]) -> list[StockBasic]:
        return []

    async def get_backward_factor(self, symbols: list[str]) -> list[BackwardFactor]:
        return []

    async def get_delist_date(self, symbol: str) -> date | None:
        return None

    async def update_stock_basic_from_api(self, symbols: list[str]) -> None:
        return None

    async def get_stock_list(self, security_type: str) -> list[str]:
        return []

    async def get_hist_code_list(
        self, security_type: str, start_date: int, end_date: int, local_path: str
    ) -> list[str]:
        return []

    async def get_listing_dates(
        self, symbols: list[str], security_type: str
    ) -> dict[str, str | None]:
        return {}

    async def get_stock_status(
        self, symbols: list[str], local_path: str
    ) -> dict[str, pd.DataFrame]:
        return {}

    async def get_stock_basic_df(self, symbols: list[str]) -> pd.DataFrame:
        return pd.DataFrame()

    async def get_code_info(self, security_type: str) -> pd.DataFrame:
        return pd.DataFrame()

    async def get_backward_factor_df(
        self, symbols: list[str], local_path: str
    ) -> pd.DataFrame:
        return pd.DataFrame()


class DummyKlineStore:
    """KlineStorePort 的 dummy 实现."""

    async def save_kline(
        self,
        data: list[KlineBar],
        interval: Interval,
    ) -> None:
        return None

    async def get_kline(
        self,
        symbol: str,
        interval: Interval,
        start: str,
        end: str,
    ) -> list[KlineBar]:
        return []

    async def get_last_sync_dates(
        self,
        symbols: list[str],
        interval: Interval,
    ) -> dict[str, date | None]:
        return {}

    async def set_last_sync_dates(
        self,
        symbol_dates: dict[str, date],
        interval: Interval,
    ) -> None:
        return None


class DummyCalendarStore:
    """CalendarStorePort 的 dummy 实现."""

    async def save_calendar(self, dates: list[date]) -> None:
        return None

    async def get_trading_calendar(self, year: int) -> list[date]:
        return []

    async def get_trading_days(self, start_date: date, end_date: date) -> list[date]:
        return []


class DummyExchangeIndexProvider:
    """ExchangeIndexProviderPort 的 dummy 实现."""

    async def get_index_constituent(
        self, code_list: list[str], local_path: str, is_local: bool = True
    ) -> dict[str, pd.DataFrame]:
        return {}

    async def get_index_weight(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        return {}

    async def get_index_code_list(self, security_type: str) -> list[str]:
        return []


class DummyExchangeIndexStore:
    """ExchangeIndexStorePort 的 dummy 实现."""

    async def save_index_constituent(self, records: list[IndexConstituent]) -> int:
        return 0

    async def save_index_weight(self, records: list[IndexWeight]) -> int:
        return 0

    async def is_index_constituent_empty(self) -> bool:
        return True


class DummyIndustryIndexProvider:
    """IndustryIndexProviderPort 的 dummy 实现."""

    async def get_industry_base_info(
        self, local_path: str, is_local: bool = True
    ) -> pd.DataFrame:
        return pd.DataFrame()

    async def get_industry_constituent(
        self, code_list: list[str], local_path: str, is_local: bool = True
    ) -> dict[str, pd.DataFrame]:
        return {}

    async def get_industry_weight(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        return {}

    async def get_industry_daily(
        self,
        code_list: list[str],
        local_path: str,
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        return {}

    async def get_industry_index_codes(self, local_path: str) -> list[str]:
        return []


class DummyIndustryIndexStore:
    """IndustryIndexStorePort 的 dummy 实现."""

    async def save_industry_base_info(self, records: list[IndustryBaseInfo]) -> int:
        return 0

    async def save_industry_constituent(
        self, records: list[IndustryConstituent]
    ) -> int:
        return 0

    async def save_industry_weight(self, records: list[IndustryWeight]) -> int:
        return 0

    async def save_industry_daily(self, records: list[IndustryDaily]) -> int:
        return 0

    async def get_industry_daily_last_date(self, index_code: str) -> str | None:
        return None

    async def is_industry_base_info_empty(self) -> bool:
        return True


# =====================================================================
# Protocol 合规性测试
# =====================================================================


class TestKlineProviderPort:
    """KlineProviderPort Protocol 合规性测试."""

    def test_dummy_is_instance(self):
        """DummyKlineProvider 应满足 KlineProviderPort Protocol."""
        dummy = DummyKlineProvider()
        assert isinstance(dummy, KlineProviderPort)

    def test_get_kline_returns_list(self):
        """get_kline 应返回 list[KlineBar]."""
        import asyncio

        dummy = DummyKlineProvider()
        result = asyncio.run(dummy.get_kline(["600000.SH"], Interval.DAY, "20240101", "20240131"))
        assert isinstance(result, list)


class TestCalendarProviderPort:
    """CalendarProviderPort Protocol 合规性测试."""

    def test_dummy_is_instance(self):
        """DummyCalendarProvider 应满足 CalendarProviderPort Protocol."""
        dummy = DummyCalendarProvider()
        assert isinstance(dummy, CalendarProviderPort)

    def test_get_trading_calendar_returns_list(self):
        """get_trading_calendar 应返回 list[date]."""
        import asyncio

        dummy = DummyCalendarProvider()
        result = asyncio.run(dummy.get_trading_calendar(2024))
        assert isinstance(result, list)


class TestReferenceProviderPort:
    """ReferenceProviderPort Protocol 合规性测试."""

    def test_dummy_is_instance(self):
        """DummyReferenceProvider 应满足 ReferenceProviderPort Protocol."""
        dummy = DummyReferenceProvider()
        assert isinstance(dummy, ReferenceProviderPort)


class TestKlineStorePort:
    """KlineStorePort Protocol 合规性测试."""

    def test_dummy_is_instance(self):
        """DummyKlineStore 应满足 KlineStorePort Protocol."""
        dummy = DummyKlineStore()
        assert isinstance(dummy, KlineStorePort)

    def test_save_kline_method_exists(self):
        """save_kline 方法应存在且为 async."""
        dummy = DummyKlineStore()
        import asyncio

        asyncio.run(dummy.save_kline([], Interval.DAY))

    def test_get_last_sync_dates_method_exists(self):
        """get_last_sync_dates 方法应存在且为 async."""
        dummy = DummyKlineStore()
        import asyncio

        result = asyncio.run(dummy.get_last_sync_dates(["600000.SH"], Interval.DAY))
        assert isinstance(result, dict)

    def test_set_last_sync_dates_method_exists(self):
        """set_last_sync_dates 方法应存在且为 async."""
        dummy = DummyKlineStore()
        import asyncio

        asyncio.run(dummy.set_last_sync_dates({"600000.SH": date(2024, 1, 15)}, Interval.DAY))


class TestCalendarStorePort:
    """CalendarStorePort Protocol 合规性测试."""

    def test_dummy_is_instance(self):
        """DummyCalendarStore 应满足 CalendarStorePort Protocol."""
        dummy = DummyCalendarStore()
        assert isinstance(dummy, CalendarStorePort)


class TestExchangeIndexProviderPort:
    """ExchangeIndexProviderPort Protocol 合规性测试."""

    def test_dummy_is_instance(self):
        """DummyExchangeIndexProvider 应满足 ExchangeIndexProviderPort Protocol."""
        dummy = DummyExchangeIndexProvider()
        assert isinstance(dummy, ExchangeIndexProviderPort)

    def test_get_index_constituent_returns_dict(self):
        """get_index_constituent 应返回 dict[str, DataFrame]."""
        import asyncio

        dummy = DummyExchangeIndexProvider()
        result = asyncio.run(
            dummy.get_index_constituent(["000300.SH"], "/tmp/cache")
        )
        assert isinstance(result, dict)

    def test_get_index_code_list_returns_list(self):
        """get_index_code_list 应返回 list[str]."""
        import asyncio

        dummy = DummyExchangeIndexProvider()
        result = asyncio.run(dummy.get_index_code_list("EXTRA_INDEX_A"))
        assert isinstance(result, list)


class TestExchangeIndexStorePort:
    """ExchangeIndexStorePort Protocol 合规性测试."""

    def test_dummy_is_instance(self):
        """DummyExchangeIndexStore 应满足 ExchangeIndexStorePort Protocol."""
        dummy = DummyExchangeIndexStore()
        assert isinstance(dummy, ExchangeIndexStorePort)

    def test_save_index_constituent_returns_int(self):
        """save_index_constituent 应返回 int."""
        import asyncio

        dummy = DummyExchangeIndexStore()
        result = asyncio.run(dummy.save_index_constituent([]))
        assert isinstance(result, int)

    def test_is_index_constituent_empty_returns_bool(self):
        """is_index_constituent_empty 应返回 bool."""
        import asyncio

        dummy = DummyExchangeIndexStore()
        result = asyncio.run(dummy.is_index_constituent_empty())
        assert isinstance(result, bool)


class TestIndustryIndexProviderPort:
    """IndustryIndexProviderPort Protocol 合规性测试."""

    def test_dummy_is_instance(self):
        """DummyIndustryIndexProvider 应满足 IndustryIndexProviderPort Protocol."""
        dummy = DummyIndustryIndexProvider()
        assert isinstance(dummy, IndustryIndexProviderPort)

    def test_get_industry_base_info_returns_dataframe(self):
        """get_industry_base_info 应返回 DataFrame."""
        import asyncio

        dummy = DummyIndustryIndexProvider()
        result = asyncio.run(dummy.get_industry_base_info("/tmp/cache"))
        assert isinstance(result, pd.DataFrame)

    def test_get_industry_daily_returns_dict(self):
        """get_industry_daily 应返回 dict[str, DataFrame]."""
        import asyncio

        dummy = DummyIndustryIndexProvider()
        result = asyncio.run(
            dummy.get_industry_daily(["801010.SI"], "/tmp/cache")
        )
        assert isinstance(result, dict)


class TestIndustryIndexStorePort:
    """IndustryIndexStorePort Protocol 合规性测试."""

    def test_dummy_is_instance(self):
        """DummyIndustryIndexStore 应满足 IndustryIndexStorePort Protocol."""
        dummy = DummyIndustryIndexStore()
        assert isinstance(dummy, IndustryIndexStorePort)

    def test_save_industry_daily_returns_int(self):
        """save_industry_daily 应返回 int."""
        import asyncio

        dummy = DummyIndustryIndexStore()
        result = asyncio.run(dummy.save_industry_daily([]))
        assert isinstance(result, int)

    def test_get_industry_daily_last_date_returns_optional_str(self):
        """get_industry_daily_last_date 应返回 str | None."""
        import asyncio

        dummy = DummyIndustryIndexStore()
        result = asyncio.run(dummy.get_industry_daily_last_date("801010.SI"))
        assert result is None

    def test_is_industry_base_info_empty_returns_bool(self):
        """is_industry_base_info_empty 应返回 bool."""
        import asyncio

        dummy = DummyIndustryIndexStore()
        result = asyncio.run(dummy.is_industry_base_info_empty())
        assert isinstance(result, bool)


class TestAllPortsImportable:
    """验证所有端口可从 domain.ports 导入."""

    def test_all_ports_importable(self):
        """9 个端口均可从 domain.ports 统一导入."""
        from galaxy_core.domain.ports import (
            CalendarProviderPort,
            CalendarStorePort,
            ExchangeIndexProviderPort,
            ExchangeIndexStorePort,
            IndustryIndexProviderPort,
            IndustryIndexStorePort,
            KlineProviderPort,
            KlineStorePort,
            ReferenceProviderPort,
        )

        # 确认导入成功（Protocol 类型本身）
        assert CalendarProviderPort is not None
        assert CalendarStorePort is not None
        assert ExchangeIndexProviderPort is not None
        assert ExchangeIndexStorePort is not None
        assert IndustryIndexProviderPort is not None
        assert IndustryIndexStorePort is not None
        assert KlineProviderPort is not None
        assert KlineStorePort is not None
        assert ReferenceProviderPort is not None
