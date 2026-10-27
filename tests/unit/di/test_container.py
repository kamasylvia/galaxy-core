"""DI 容器单元测试.

验证 dependency-injector DeclarativeContainer 绑定正确性和 create_container 工厂函数。
"""

from unittest.mock import MagicMock, patch

from dependency_injector import containers

from galaxy_core.services.calendar_data_service import CalendarDataService
from galaxy_core.services.kline_data_service import KlineDataService
from galaxy_core.services.reference_data_service import ReferenceDataService


class TestContainerStructure:
    """验证 Container 类结构."""

    def test_container_is_declarative_container(self):
        """Container 应继承 containers.DeclarativeContainer."""
        from galaxy_core.di.container import Container

        assert issubclass(Container, containers.DeclarativeContainer)

    def test_container_has_config_provider(self):
        """Container 应包含 config = providers.Configuration()."""
        from galaxy_core.di.container import Container

        assert hasattr(Container, "config")
        # providers.Configuration 在类级别是 Provider 等级的属性
        from dependency_injector import providers

        assert isinstance(Container.config, providers.Configuration)

    def test_container_has_db_manager_singleton(self):
        """Container 应包含 db_manager = providers.Singleton(AsyncDatabaseManager)."""
        from galaxy_core.di.container import Container

        assert hasattr(Container, "db_manager")
        from dependency_injector import providers

        assert isinstance(Container.db_manager, providers.Singleton)

    def test_container_has_amazing_data_client_singleton(self):
        """Container 应包含 amazing_data_client = providers.Singleton(...)."""
        from galaxy_core.di.container import Container

        assert hasattr(Container, "amazing_data_client")
        from dependency_injector import providers

        assert isinstance(Container.amazing_data_client, providers.Singleton)


class TestContainerProviderBindings:
    """验证 Container provider 绑定."""

    def test_container_has_kline_provider(self):
        """Container 应包含 kline_provider singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "kline_provider")
        assert isinstance(Container.kline_provider, providers.Singleton)

    def test_container_has_calendar_provider(self):
        """Container 应包含 calendar_provider singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "calendar_provider")
        assert isinstance(Container.calendar_provider, providers.Singleton)

    def test_container_has_reference_provider(self):
        """Container 应包含 reference_provider singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "reference_provider")
        assert isinstance(Container.reference_provider, providers.Singleton)

    def test_container_has_kline_store(self):
        """Container 应包含 kline_store singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "kline_store")
        assert isinstance(Container.kline_store, providers.Singleton)

    def test_container_has_calendar_store(self):
        """Container 应包含 calendar_store singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "calendar_store")
        assert isinstance(Container.calendar_store, providers.Singleton)


class TestContainerIndexBindings:
    """验证 Container 指数数据（exchange + industry index）provider/store/job 绑定."""

    def test_container_has_exchange_index_provider(self):
        """Container 应包含 exchange_index_provider singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "exchange_index_provider")
        assert isinstance(Container.exchange_index_provider, providers.Singleton)

    def test_container_has_industry_index_provider(self):
        """Container 应包含 industry_index_provider singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "industry_index_provider")
        assert isinstance(Container.industry_index_provider, providers.Singleton)

    def test_container_has_exchange_index_store(self):
        """Container 应包含 exchange_index_store singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "exchange_index_store")
        assert isinstance(Container.exchange_index_store, providers.Singleton)

    def test_container_has_industry_index_store(self):
        """Container 应包含 industry_index_store singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "industry_index_store")
        assert isinstance(Container.industry_index_store, providers.Singleton)

    def test_container_has_exchange_index_job(self):
        """Container 应包含 exchange_index_job singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "exchange_index_job")
        assert isinstance(Container.exchange_index_job, providers.Singleton)

    def test_container_has_industry_index_job(self):
        """Container 应包含 industry_index_job singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "industry_index_job")
        assert isinstance(Container.industry_index_job, providers.Singleton)

class TestContainerDatabaseServices:
    """验证 Container database/services 层绑定."""

    def test_container_has_kline_db_service(self):
        """Container 应包含 kline_db_service singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "kline_db_service")
        assert isinstance(Container.kline_db_service, providers.Singleton)

    def test_container_has_trading_calendar_service(self):
        """Container 应包含 trading_calendar_service singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "trading_calendar_service")
        assert isinstance(Container.trading_calendar_service, providers.Singleton)


class TestContainerApplicationServices:
    """验证 Container 应用服务层绑定."""

    def test_container_has_kline_service(self):
        """Container 应包含 kline_service singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "kline_service")
        assert isinstance(Container.kline_service, providers.Singleton)

    def test_container_has_calendar_service(self):
        """Container 应包含 calendar_service singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "calendar_service")
        assert isinstance(Container.calendar_service, providers.Singleton)

    def test_container_has_reference_service(self):
        """Container 应包含 reference_service singleton."""
        from galaxy_core.di.container import Container
        from dependency_injector import providers

        assert hasattr(Container, "reference_service")
        assert isinstance(Container.reference_service, providers.Singleton)


class TestCreateContainer:
    """验证 create_container 工厂函数."""

    def test_create_container_returns_container_with_config(self):
        """create_container() 应返回包含 config 属性的容器."""
        from galaxy_core.di.container import create_container, Container
        from dependency_injector import containers

        result = create_container()

        assert isinstance(result, containers.Container)
        assert hasattr(result, "config")
        assert hasattr(result, "db_manager")
        assert hasattr(result, "kline_service")

    def test_create_container_no_injector_import(self):
        """container.py 不应导入 injector 框架."""
        with open(
            "data/src/galaxy_core/di/container.py", encoding="utf-8"
        ) as f:
            content = f.read()

        assert "from injector import" not in content, "container.py 不应导入 injector 框架"
        assert "import injector" not in content, "container.py 不应导入 injector 框架"


class TestServiceResolution:
    """验证服务可从 DI 容器解析."""

    def test_container_provides_kline_data_service(self):
        """create_container() 返回的容器应能创建 KlineDataService 实例."""
        from galaxy_core.di.container import Container

        container = Container()
        mock_db = MagicMock()
        mock_client = MagicMock()

        with container.db_manager.override(mock_db), \
             container.amazing_data_client.override(mock_client):
            service = container.kline_service()

        assert isinstance(service, KlineDataService)

    def test_container_provides_calendar_data_service(self):
        """create_container() 返回的容器应能创建 CalendarDataService 实例."""
        from galaxy_core.di.container import Container

        container = Container()
        mock_db = MagicMock()
        mock_client = MagicMock()

        with container.db_manager.override(mock_db), \
             container.amazing_data_client.override(mock_client):
            service = container.calendar_service()

        assert isinstance(service, CalendarDataService)

    def test_container_provides_reference_data_service(self):
        """create_container() 返回的容器应能创建 ReferenceDataService 实例."""
        from galaxy_core.di.container import Container

        container = Container()
        mock_db = MagicMock()
        mock_client = MagicMock()

        with container.db_manager.override(mock_db), \
             container.amazing_data_client.override(mock_client):
            service = container.reference_service()

        assert isinstance(service, ReferenceDataService)
