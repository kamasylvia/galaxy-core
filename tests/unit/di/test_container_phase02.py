"""DI 容器 Phase 02 provider 绑定单元测试.

验证 02-08 注册的新 provider(范围修订后:akshare_provider + 2 store adapter
+ 1 job factory,baostock 整源删)+ akshare 无 client 注入不变量,
并回归确认 Phase 01 指数 job 未被破坏。

不连真实 DB/SDK:用 container.<provider>.override(mock) 隔离,
akshare 无 client 通过 Singleton 依赖键集合断言。

2026-06-19 范围修订(见 02-SCOPE-REVISION-REPORT.md):baostock 整源删,
相关 provider/job 全删。
"""

from unittest.mock import MagicMock

from dependency_injector import providers


class TestContainerPhase02Providers:
    """验证 Container Phase 02 新增 provider 绑定(范围修订后)."""

    def test_container_has_akshare_provider_singleton(self):
        """Container 应包含 akshare_provider singleton."""
        from galaxy_core.di.container import Container

        assert hasattr(Container, "akshare_provider")
        assert isinstance(Container.akshare_provider, providers.Singleton)

    def test_container_has_fund_flow_amazing_provider_singleton(self):
        """Container 应包含 fund_flow_amazing_provider singleton."""
        from galaxy_core.di.container import Container

        assert hasattr(Container, "fund_flow_amazing_provider")
        assert isinstance(Container.fund_flow_amazing_provider, providers.Singleton)

    def test_container_has_akshare_store_singleton(self):
        """Container 应包含 akshare_store singleton."""
        from galaxy_core.di.container import Container

        assert hasattr(Container, "akshare_store")
        assert isinstance(Container.akshare_store, providers.Singleton)

    def test_container_has_fund_flow_amazing_store_singleton(self):
        """Container 应包含 fund_flow_amazing_store singleton."""
        from galaxy_core.di.container import Container

        assert hasattr(Container, "fund_flow_amazing_store")
        assert isinstance(Container.fund_flow_amazing_store, providers.Singleton)

    def test_container_has_fundflow_job_singleton(self):
        """Container 应包含 fundflow_job singleton."""
        from galaxy_core.di.container import Container

        assert hasattr(Container, "fundflow_job")
        assert isinstance(Container.fundflow_job, providers.Singleton)

    def test_container_has_no_baostock_providers(self):
        """范围修订回归:baostock 整源删,Container 不应有 baostock_* provider."""
        from galaxy_core.di.container import Container

        for name in ("baostock_client", "baostock_provider", "baostock_store", "baostock_job"):
            assert not hasattr(Container, name), f"Container 不应再含 {name}(baostock 整源删)"


class TestAkshareProviderNoClientDependency:
    """关键不变量:akshare_provider 无 client 参数(stateless lib, D-06)."""

    def test_akshare_provider_has_no_client_kwarg(self):
        """akshare_provider 的依赖键不应包含 client.

        dependency-injector Singleton 通过 provider.args / provider.kwargs
        暴露注入参数;akshare 是 stateless,无 client 注入。
        """
        from galaxy_core.di.container import Container

        singleton = Container.akshare_provider
        # Singleton 的注入参数聚合在 deps(位置参数)与 kwargs(关键字参数)
        has_client_arg = any(
            getattr(a, "name", None) == "client" or "client" in repr(a)
            for a in singleton.args
        )
        has_client_kw = "client" in dict(singleton.kwargs)
        assert not has_client_arg, (
            f"akshare_provider 不应注入 client(位置参数),实际 args={singleton.args}"
        )
        assert not has_client_kw, (
            f"akshare_provider 不应注入 client(关键字参数),实际 kwargs={dict(singleton.kwargs)}"
        )

    def test_fund_flow_amazing_provider_injects_amazing_data_client(self):
        """对比回归:fund_flow_amazing_provider 应注入 client(复用 amazing_data_client)."""
        from galaxy_core.di.container import Container

        singleton = Container.fund_flow_amazing_provider
        kwargs = dict(singleton.kwargs)
        assert "client" in kwargs, (
            f"fund_flow_amazing_provider 应注入 client,实际 kwargs={kwargs}"
        )


class TestJobFactoriesExist:
    """验证 _create_fundflow_job staticmethod 存在(范围修订后仅 1)."""

    def test_container_has_create_fundflow_job_staticmethod(self):
        from galaxy_core.di.container import Container

        assert hasattr(Container, "_create_fundflow_job")
        # staticmethod 在类上访问应是普通 callable(无 self/cls 绑定)
        assert callable(Container._create_fundflow_job)

    def test_container_has_no_create_baostock_job(self):
        """范围修订回归:_create_baostock_job 应已删."""
        from galaxy_core.di.container import Container

        assert not hasattr(Container, "_create_baostock_job"), (
            "_create_baostock_job 应已删(baostock 整源删)"
        )


class TestJobInjectionDeps:
    """验证 job provider 注入正确的依赖数量."""

    def test_fundflow_job_injects_9_deps(self):
        """fundflow_job 应注入 9 个依赖(Phase 03 加 last_sync_date_store;
        2026-06-25 加 reference_provider 修复 per-symbol 表漏取;
        2026-07-28 加 db_manager 用于 universe DB fallback;
        2026-09-09 加 calendar_store 用于 margin_detail 空结果熔断):
        sync_state_manager + akshare_provider + fund_flow_amazing_provider
        + akshare_store + fund_flow_amazing_store + last_sync_date_store
        + reference_provider + db_manager + calendar_store."""
        from galaxy_core.di.container import Container

        singleton = Container.fundflow_job
        kwargs = dict(singleton.kwargs)
        expected = {
            "sync_state_manager",
            "akshare_provider",
            "fund_flow_amazing_provider",
            "akshare_store",
            "fund_flow_amazing_store",
            "last_sync_date_store",
            "reference_provider",
            "db_manager",
            "calendar_store",
        }
        assert set(kwargs.keys()) == expected, (
            f"fundflow_job 注入键不匹配,期望 {expected},实际 {set(kwargs.keys())}"
        )

    def test_fundflow_job_resolves_to_fundflow_sync_job(self):
        """实例化 fundflow_job 应得到 FundFlowSyncJob(mock 掉 7 依赖避免真实连接)."""
        from galaxy_core.application.scheduler.jobs.fundflow_sync_job import (
            FundFlowSyncJob,
        )
        from galaxy_core.di.container import Container

        container = Container()
        mocks = {name: MagicMock() for name in (
            "sync_state_manager", "akshare_provider", "fund_flow_amazing_provider",
            "akshare_store", "fund_flow_amazing_store", "last_sync_date_store",
            "reference_provider",
        )}
        with container.sync_state_manager.override(mocks["sync_state_manager"]), \
             container.akshare_provider.override(mocks["akshare_provider"]), \
             container.fund_flow_amazing_provider.override(mocks["fund_flow_amazing_provider"]), \
             container.akshare_store.override(mocks["akshare_store"]), \
             container.fund_flow_amazing_store.override(mocks["fund_flow_amazing_store"]), \
             container.last_sync_date_store.override(mocks["last_sync_date_store"]), \
             container.reference_provider.override(mocks["reference_provider"]):
            job = container.fundflow_job()
        assert isinstance(job, FundFlowSyncJob)


class TestExistingIndexStillWired:
    """回归:Phase 01 指数 job 注册未受 Phase 02 影响."""

    def test_exchange_index_job_still_singleton(self):
        from galaxy_core.di.container import Container

        assert isinstance(Container.exchange_index_job, providers.Singleton)

    def test_industry_index_job_still_singleton(self):
        from galaxy_core.di.container import Container

        assert isinstance(Container.industry_index_job, providers.Singleton)

    def test_exchange_index_job_injects_4_deps(self):
        """回归:exchange_index_job 注入 4 依赖(Phase 03 加 last_sync_date_store).

        sync_state_manager + exchange_index_provider + exchange_index_store
        + last_sync_date_store(Phase 03 增量用)。
        """
        from galaxy_core.di.container import Container

        kwargs = dict(Container.exchange_index_job.kwargs)
        assert set(kwargs.keys()) == {
            "sync_state_manager", "exchange_index_provider", "exchange_index_store",
            "last_sync_date_store",
        }
