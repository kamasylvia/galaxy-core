"""DI 容器 — 使用 dependency-injector 管理 service/adapter 生命周期."""

from typing import Any

from dependency_injector import containers, providers

from galaxy_core.amazing_data.api.adapters.calendar_provider_adapter import (
    CalendarProviderAdapter,
)

# Adapter imports
from galaxy_core.amazing_data.api.adapters.exchange_index_provider_adapter import (
    ExchangeIndexProviderAdapter,
)
from galaxy_core.amazing_data.api.adapters.financial_data_provider_adapter import (
    InfoDataProviderAdapter,
)
from galaxy_core.amazing_data.api.adapters.industry_index_provider_adapter import (
    IndustryIndexProviderAdapter,
)
from galaxy_core.amazing_data.api.adapters.kline_provider_adapter import KlineProviderAdapter
from galaxy_core.amazing_data.api.adapters.reference_provider_adapter import (
    ReferenceProviderAdapter,
)
from galaxy_core.amazing_data.api.adapters.fund_flow_provider_adapter import (
    FundFlowProviderAdapter,
)
from galaxy_core.amazing_data.api.client import AmazingDataClient
from galaxy_core.amazing_data.api.lazy_client import LazyAmazingDataClient
from galaxy_core.application.scheduler.jobs.exchange_index_sync_job import (
    ExchangeIndexSyncJob,
)
from galaxy_core.application.scheduler.jobs.industry_index_sync_job import (
    IndustryIndexSyncJob,
)
from galaxy_core.application.scheduler.jobs.fundflow_sync_job import (
    FundFlowSyncJob,
)
from galaxy_core.database.core.async_connection import AsyncDatabaseManager
from galaxy_core.database.services.adapters.calendar_store_adapter import CalendarStoreAdapter
from galaxy_core.database.services.adapters.exchange_index_store_adapter import (
    ExchangeIndexStoreAdapter,
)
from galaxy_core.database.services.adapters.financial_data_store_adapter import (
    FinancialDataStoreAdapter,
)
from galaxy_core.database.services.adapters.industry_index_store_adapter import (
    IndustryIndexStoreAdapter,
)
from galaxy_core.database.services.adapters.kline_store_adapter import KlineStoreAdapter
from galaxy_core.database.services.last_sync_date_store import LastSyncDateStore
from galaxy_core.database.services.adapters.akshare_store_adapter import (
    AkshareStoreAdapter,
)
from galaxy_core.database.services.adapters.fund_flow_store_adapter import (
    FundFlowStoreAdapter,
)

# Database service imports
from galaxy_core.database.services.kline import KlineService
from galaxy_core.database.services.trading_calendar import TradingCalendarService

# Port imports
from galaxy_core.services.calendar_data_service import CalendarDataService

# Third-party provider adapter imports (akshare; baostock 整源删 2026-06-19)
from galaxy_core.third_party.akshare.adapters.akshare_fund_flow_adapter import (
    AkshareFundFlowProviderAdapter,
)

# Service imports
from galaxy_core.services.financial_data_service import FinancialDataService
from galaxy_core.services.kline_data_service import KlineDataService
from galaxy_core.services.reference_data_service import ReferenceDataService


def _create_async_db_manager() -> AsyncDatabaseManager:
    """创建并初始化 AsyncDatabaseManager 实例."""
    manager = AsyncDatabaseManager()
    manager.initialize()
    return manager


def _create_lazy_amazing_client() -> LazyAmazingDataClient:
    """创建懒登录 AmazingData 客户端代理(2026-10-26 TGW 互踢修复).

    构造 ≠ 登录:scheduler 启动构造链、白天窗口(09:00-15:30,含 11:50
    refresh 重启)一律不触发 SDK 登录;首次实际 SDK 方法调用(凌晨 00:10
    全量链等)才经 from_config 登录。TGW 单会话互踢详见 lazy_client.py。
    """
    return LazyAmazingDataClient(AmazingDataClient.from_config)


class Container(containers.DeclarativeContainer):
    """应用 DI 容器 — 声明式定义所有 provider.

    使用 dependency-injector 的 DeclarativeContainer 模式，
    所有依赖关系显式声明在类级别。
    """

    # === 配置层 ===
    config = providers.Configuration()

    # === 基础设施层（Singleton）===
    db_manager = providers.Singleton(_create_async_db_manager)

    amazing_data_client = providers.Singleton(
        _create_lazy_amazing_client,
    )

    # === Provider Adapters（Singleton）===
    kline_provider = providers.Singleton(
        KlineProviderAdapter,
        client=amazing_data_client,
    )

    calendar_provider = providers.Singleton(
        CalendarProviderAdapter,
        client=amazing_data_client,
    )

    reference_provider = providers.Singleton(
        ReferenceProviderAdapter,
        client=amazing_data_client,
    )

    financial_provider = providers.Singleton(
        InfoDataProviderAdapter,
        client=amazing_data_client,
    )

    exchange_index_provider = providers.Singleton(
        ExchangeIndexProviderAdapter,
        client=amazing_data_client,
    )

    industry_index_provider = providers.Singleton(
        IndustryIndexProviderAdapter,
        client=amazing_data_client,
    )

    # --- Phase 02: 资金流向多源 provider adapters(2026-06-19 范围修订:baostock 删) ---

    # akshare(stateless lib,无 client 注入 — D-06)
    akshare_provider = providers.Singleton(AkshareFundFlowProviderAdapter)

    # AmazingData 资金流向(复用 amazing_data_client — D-07)
    fund_flow_amazing_provider = providers.Singleton(
        FundFlowProviderAdapter,
        client=amazing_data_client,
    )

    # === Store Adapters（Singleton）===
    kline_store = providers.Singleton(
        KlineStoreAdapter,
        db_manager=db_manager,
    )

    calendar_store = providers.Singleton(
        CalendarStoreAdapter,
        db_manager=db_manager,
    )

    financial_store = providers.Singleton(
        FinancialDataStoreAdapter,
        db_manager=db_manager,
    )

    exchange_index_store = providers.Singleton(
        ExchangeIndexStoreAdapter,
        db_manager=db_manager,
    )

    industry_index_store = providers.Singleton(
        IndustryIndexStoreAdapter,
        db_manager=db_manager,
    )

    # --- Phase 02: store adapters(范围修订后:baostock 删) ---
    akshare_store = providers.Singleton(
        AkshareStoreAdapter,
        db_manager=db_manager,
    )
    fund_flow_amazing_store = providers.Singleton(
        FundFlowStoreAdapter,
        db_manager=db_manager,
    )

    @staticmethod
    def _create_sync_state_manager(db_manager: AsyncDatabaseManager) -> Any:
        """延迟创建 SyncStateManager，避免循环导入."""
        from galaxy_core.application.scheduler.state_manager import SyncStateManager

        return SyncStateManager(db_manager=db_manager)

    sync_state_manager = providers.Singleton(_create_sync_state_manager, db_manager=db_manager)

    # === Phase 03: last_sync_date 通用 store（Phase 1&2 表增量用, 03-02）===
    last_sync_date_store = providers.Singleton(LastSyncDateStore, db_manager=db_manager)

    # === Database Services（Singleton，构造函数注入）===
    kline_db_service = providers.Singleton(
        KlineService,
        db_manager=db_manager,
    )

    trading_calendar_service = providers.Singleton(
        TradingCalendarService,
        db_manager=db_manager,
        calendar_store=calendar_store,
    )

    # === Application Services（Singleton）===
    kline_service = providers.Singleton(
        KlineDataService,
        kline_provider=kline_provider,
        kline_store=kline_store,
        reference_provider=reference_provider,
        calendar_store=calendar_store,
    )

    calendar_service = providers.Singleton(
        CalendarDataService,
        calendar_provider=calendar_provider,
        calendar_store=calendar_store,
    )

    reference_service = providers.Singleton(
        ReferenceDataService,
        reference_provider=reference_provider,
        db_manager=db_manager,
    )

    financial_service = providers.Singleton(
        FinancialDataService,
        provider=financial_provider,
        store=financial_store,
        reference_provider=reference_provider,
        db_manager=db_manager,
    )

    # === Scheduler Jobs（Singleton，延迟注入 sync_state_manager）===
    @staticmethod
    def _create_exchange_index_job(
        sync_state_manager, exchange_index_provider, exchange_index_store,
        last_sync_date_store,
    ) -> Any:
        """延迟创建 ExchangeIndexSyncJob，注入 sync_state_manager + last_sync_date_store(Phase 03)."""
        return ExchangeIndexSyncJob(
            state_manager=sync_state_manager,
            provider=exchange_index_provider,
            store=exchange_index_store,
            last_sync_store=last_sync_date_store,
        )

    exchange_index_job = providers.Singleton(
        _create_exchange_index_job,
        sync_state_manager=sync_state_manager,
        exchange_index_provider=exchange_index_provider,
        exchange_index_store=exchange_index_store,
        last_sync_date_store=last_sync_date_store,
    )

    @staticmethod
    def _create_industry_index_job(
        sync_state_manager, industry_index_provider, industry_index_store,
        last_sync_date_store, calendar_store,
    ) -> Any:
        """延迟创建 IndustryIndexSyncJob，注入 sync_state_manager + last_sync_date_store(Phase 03)
        + calendar_store(2026-09-11,industry_daily 覆盖率熔断)."""
        return IndustryIndexSyncJob(
            state_manager=sync_state_manager,
            provider=industry_index_provider,
            store=industry_index_store,
            last_sync_store=last_sync_date_store,
            calendar_store=calendar_store,
        )

    industry_index_job = providers.Singleton(
        _create_industry_index_job,
        sync_state_manager=sync_state_manager,
        industry_index_provider=industry_index_provider,
        industry_index_store=industry_index_store,
        last_sync_date_store=last_sync_date_store,
        calendar_store=calendar_store,
    )

    # --- Phase 02: 资金流向同步任务(延迟注入 sync_state_manager, 2026-06-19 范围修订后仅 fundflow)---
    @staticmethod
    def _create_fundflow_job(
        sync_state_manager,
        akshare_provider,
        fund_flow_amazing_provider,
        akshare_store,
        fund_flow_amazing_store,
        last_sync_date_store,
        reference_provider,
        db_manager,
        calendar_store,
    ) -> Any:
        """延迟创建 FundFlowSyncJob,注入 9 依赖(Phase 03 加 last_sync_date_store;
        2026-06-25 加 reference_provider 修复 per-symbol 表漏取;
        2026-07-28 加 db_manager 用于 universe DB fallback;
        2026-09-09 加 calendar_store 用于 margin_detail 空结果熔断)."""
        return FundFlowSyncJob(
            state_manager=sync_state_manager,
            akshare_provider=akshare_provider,
            amazing_provider=fund_flow_amazing_provider,
            akshare_store=akshare_store,
            amazing_store=fund_flow_amazing_store,
            last_sync_store=last_sync_date_store,
            reference_provider=reference_provider,
            db_manager=db_manager,
            calendar_store=calendar_store,
        )

    fundflow_job = providers.Singleton(
        _create_fundflow_job,
        sync_state_manager=sync_state_manager,
        akshare_provider=akshare_provider,
        fund_flow_amazing_provider=fund_flow_amazing_provider,
        akshare_store=akshare_store,
        fund_flow_amazing_store=fund_flow_amazing_store,
        last_sync_date_store=last_sync_date_store,
        reference_provider=reference_provider,
        db_manager=db_manager,
        calendar_store=calendar_store,
    )


def create_container() -> Container:
    """创建应用 DI 容器.

    Returns:
        Container: 配置完成的容器实例
    """
    from galaxy_core.shared_kernel.utils.config_loader import load_config_dict

    container = Container()

    # 从 config_loader 加载配置
    config_dict = load_config_dict()
    container.config.from_dict(config_dict)

    return container
