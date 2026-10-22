"""ReferenceDataService 单元测试."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from galaxy_core.domain.value_objects import SecurityType, StockBasic
from galaxy_core.services.reference_data_service import ReferenceDataService


class TestReferenceDataServiceConstruction:
    """验证构造函数签名和端口依赖."""

    def test_constructor_accepts_port_dependencies(self):
        """ReferenceDataService 构造函数应接收 ReferenceProviderPort 和 AsyncDatabaseManager."""
        provider = MagicMock()
        db_manager = MagicMock()

        service = ReferenceDataService(
            reference_provider=provider,
            db_manager=db_manager,
        )

        assert service._provider is provider
        assert service._db is db_manager

    def test_service_has_sync_method(self):
        """ReferenceDataService 应有 sync 方法."""
        service = ReferenceDataService(
            reference_provider=MagicMock(),
            db_manager=MagicMock(),
        )

        assert hasattr(service, "sync")
        assert callable(service.sync)


class TestReferenceDataServiceSync:
    """验证 sync 方法行为."""

    @pytest.mark.asyncio
    async def test_sync_calls_provider_get_stock_basic(self):
        """sync 应调用 provider.get_stock_basic."""
        provider = AsyncMock()
        db_manager = MagicMock()

        mock_stock = StockBasic(
            symbol="510050.SH",
            security_type=SecurityType.EXTRA_ETF,
            list_date="20050223",
            delist_date=None,
            stock_name="50ETF",
            market="SH",
            exchange="SH",
        )
        provider.get_stock_basic.return_value = [mock_stock]
        provider.get_backward_factor.return_value = []

        service = ReferenceDataService(provider, db_manager)
        await service.sync(security_type="EXTRA_ETF", today=date(2024, 1, 15))

        provider.get_stock_basic.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_calls_provider_get_backward_factor(self):
        """sync 应调用 provider.get_backward_factor."""
        provider = AsyncMock()
        db_manager = MagicMock()

        mock_stock = StockBasic(
            symbol="510050.SH",
            security_type=SecurityType.EXTRA_ETF,
            list_date="20050223",
            delist_date=None,
            stock_name="50ETF",
            market="SH",
            exchange="SH",
        )
        provider.get_stock_basic.return_value = [mock_stock]
        provider.get_backward_factor.return_value = []

        service = ReferenceDataService(provider, db_manager)
        await service.sync(security_type="EXTRA_ETF", today=date(2024, 1, 15))

        provider.get_backward_factor.assert_called_once_with(symbols=["510050.SH"])
