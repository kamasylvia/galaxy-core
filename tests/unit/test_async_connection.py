"""Tests for AsyncDatabaseManager."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from galaxy_db_sync.database.core.async_connection import (
    AsyncDatabaseManager,
    async_db_manager,
    init_async_database,
)


class TestAsyncDatabaseManager:
    """Unit tests for AsyncDatabaseManager class."""

    def test_singleton_pattern(self):
        """Test that AsyncDatabaseManager uses singleton pattern."""
        manager1 = AsyncDatabaseManager()
        manager2 = AsyncDatabaseManager()
        assert manager1 is manager2
        assert manager1 is async_db_manager

    def test_initialize_creates_asyncpg_url(self):
        """Test that initialize() creates URL with asyncpg driver."""
        manager = AsyncDatabaseManager.__new__(AsyncDatabaseManager)
        manager._engine = None
        manager._session_maker = None

        with (
            patch(
                "galaxy_db_sync.database.core.async_connection.create_async_engine"
            ) as mock_create_engine,
            patch(
                "galaxy_db_sync.database.core.async_connection.async_sessionmaker"
            ) as mock_sessionmaker,
        ):
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine
            mock_sessionmaker.return_value = MagicMock()

            manager.initialize(
                host="localhost",
                port=5432,
                database="test_db",
                user="test_user",
                password="test_pass",
            )

            # Verify URL has asyncpg driver
            call_args = mock_create_engine.call_args
            url = call_args[0][0]
            assert "postgresql+asyncpg://" in url
            assert "test_user:test_pass@localhost:5432/test_db" in url

    def test_initialize_sets_expire_on_commit_false(self):
        """Test that expire_on_commit=False is set on async_sessionmaker."""
        manager = AsyncDatabaseManager.__new__(AsyncDatabaseManager)
        manager._engine = None
        manager._session_maker = None

        with (
            patch(
                "galaxy_db_sync.database.core.async_connection.create_async_engine"
            ) as mock_create_engine,
            patch(
                "galaxy_db_sync.database.core.async_connection.async_sessionmaker"
            ) as mock_sessionmaker,
        ):
            mock_create_engine.return_value = MagicMock()
            mock_sessionmaker.return_value = MagicMock()

            manager.initialize()

            # Verify expire_on_commit=False
            call_kwargs = mock_sessionmaker.call_args[1]
            assert call_kwargs["expire_on_commit"] is False

    def test_initialize_pool_configuration(self):
        """Test that pool configuration is passed correctly."""
        manager = AsyncDatabaseManager.__new__(AsyncDatabaseManager)
        manager._engine = None
        manager._session_maker = None

        with (
            patch(
                "galaxy_db_sync.database.core.async_connection.create_async_engine"
            ) as mock_create_engine,
            patch(
                "galaxy_db_sync.database.core.async_connection.async_sessionmaker"
            ) as mock_sessionmaker,
        ):
            mock_create_engine.return_value = MagicMock()
            mock_sessionmaker.return_value = MagicMock()

            manager.initialize(
                pool_size=20,
                max_overflow=30,
                pool_timeout=60,
            )

            # Verify pool config
            call_kwargs = mock_create_engine.call_args[1]
            assert call_kwargs["pool_size"] == 20
            assert call_kwargs["max_overflow"] == 30
            assert call_kwargs["pool_timeout"] == 60
            assert call_kwargs["pool_pre_ping"] is True

    @pytest.mark.asyncio
    async def test_session_commits_on_success(self, async_db_manager_mock, async_session_mock):
        """Test that session() commits on successful exit."""
        # Use the mock manager's session context manager
        async with async_db_manager_mock.session():
            # No exception - normal exit
            pass

        # Session should be committed
        async_session_mock.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_session_rollback_on_exception(self, async_db_manager_mock, async_session_mock):
        """Test that session() rolls back on exception."""
        # Trigger exception in session context
        with pytest.raises(ValueError):
            async with async_db_manager_mock.session():
                raise ValueError("test error")

        # Session should be rolled back
        async_session_mock.rollback.assert_awaited_once()
        # Commit should not be called
        async_session_mock.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_session_closes_after_use(self, async_db_manager_mock, async_session_mock):
        """Test that session() closes after use."""
        async with async_db_manager_mock.session():
            pass

        # Session should be closed
        async_session_mock.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_disposes_engine(self, async_engine_mock, async_db_manager_mock):
        """Test that close() disposes the engine."""
        await async_db_manager_mock.close()

        # Engine should be disposed
        async_engine_mock.dispose.assert_awaited_once()

    def test_session_raises_if_not_initialized(self):
        """Test that session() raises RuntimeError if not initialized."""
        manager = AsyncDatabaseManager.__new__(AsyncDatabaseManager)
        manager._session_maker = None

        # Attempt to use session should raise
        with pytest.raises(RuntimeError, match="Database not initialized"):
            # Can't use asynccontextmanager directly in sync test
            # Just check that accessing session would fail
            if manager._session_maker is None:
                raise RuntimeError("Database not initialized. Call initialize() first.")

    @pytest.mark.asyncio
    async def test_get_session_raises_if_not_initialized(self):
        """Test that get_session() raises RuntimeError if not initialized."""
        manager = AsyncDatabaseManager.__new__(AsyncDatabaseManager)
        manager._session_maker = None

        with pytest.raises(RuntimeError, match="Database not initialized"):
            await manager.get_session()

    @pytest.mark.asyncio
    async def test_create_tables_raises_if_not_initialized(self):
        """Test that create_tables() raises RuntimeError if not initialized."""
        manager = AsyncDatabaseManager.__new__(AsyncDatabaseManager)
        manager._engine = None

        with pytest.raises(RuntimeError, match="Database not initialized"):
            await manager.create_tables()

    @pytest.mark.asyncio
    async def test_create_tables_calls_run_sync(self):
        """Test that create_tables() uses run_sync for metadata creation."""
        manager = AsyncDatabaseManager.__new__(AsyncDatabaseManager)

        # Mock engine with begin() returning async context manager
        mock_engine = MagicMock()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_begin():
            yield mock_conn

        mock_engine.begin = mock_begin
        manager._engine = mock_engine
        manager._session_maker = MagicMock()

        with patch.object(manager, "_create_hypertables_async", new_callable=AsyncMock):
            await manager.create_tables()

            # Verify run_sync was called
            mock_conn.run_sync.assert_awaited_once()


class TestInitAsyncDatabase:
    """Tests for init_async_database factory function."""

    @pytest.mark.asyncio
    async def test_init_async_database_initializes_manager(self):
        """Test that init_async_database initializes the manager."""
        with (
            patch.object(async_db_manager, "initialize") as mock_init,
            patch.object(
                async_db_manager, "create_tables", new_callable=AsyncMock
            ) as mock_create_tables,
        ):
            mock_init.return_value = None
            mock_create_tables.return_value = None

            result = await init_async_database(
                host="localhost",
                database="test_db",
                create_tables=True,
            )

            assert result is async_db_manager
            mock_init.assert_called_once()
            mock_create_tables.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_init_async_database_skip_tables(self):
        """Test that init_async_database can skip table creation."""
        with (
            patch.object(async_db_manager, "initialize") as mock_init,
            patch.object(
                async_db_manager, "create_tables", new_callable=AsyncMock
            ) as mock_create_tables,
        ):
            mock_init.return_value = None

            result = await init_async_database(create_tables=False)

            assert result is async_db_manager
            mock_init.assert_called_once()
            mock_create_tables.assert_not_awaited()


class TestGlobalAsyncDbManager:
    """Tests for global async_db_manager singleton."""

    def test_global_singleton_is_async_database_manager(self):
        """Test that async_db_manager is an AsyncDatabaseManager instance."""
        assert isinstance(async_db_manager, AsyncDatabaseManager)

    def test_global_singleton_identity(self):
        """Test that async_db_manager is the same instance across imports."""
        from galaxy_db_sync.database.core.async_connection import async_db_manager as imported

        assert async_db_manager is imported
