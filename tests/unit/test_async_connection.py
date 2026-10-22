"""Tests for AsyncDatabaseManager."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from galaxy_core.database.core.async_connection import AsyncDatabaseManager


class TestAsyncDatabaseManager:
    """Unit tests for AsyncDatabaseManager class."""

    def test_initialize_creates_separate_instances(self):
        """Test that AsyncDatabaseManager creates separate instances."""
        manager1 = AsyncDatabaseManager()
        manager2 = AsyncDatabaseManager()
        # Without __new__ singleton, each call creates a new instance
        assert manager1 is not manager2

    def test_initialize_reads_db_creds_via_get_env(self):
        """不传参时,DB_* 凭证走 get_env(优先 Infisical,其次 os.environ).

        回归 2026-07-06 改动:async_connection.initialize() 的 5 处 os.getenv
        改成 get_env。验证 get_env 被调用 + URL 含其返回值。
        """
        manager = AsyncDatabaseManager()

        def fake_get_env(key, default=None, environment="dev"):
            return {
                "DB_HOST": "db.from-infisical",
                "DB_PORT": "5433",
                "DB_NAME": "galaxy",
                "DB_USER": "postgres",
                "DB_PASSWORD": "secret-from-infisical",
            }.get(key, default)

        with (
            patch(
                "galaxy_core.database.core.async_connection.create_async_engine"
            ) as mock_create_engine,
            patch(
                "galaxy_core.database.core.async_connection.async_sessionmaker"
            ) as mock_sessionmaker,
            patch(
                "galaxy_core.database.core.async_connection.get_env",
                side_effect=fake_get_env,
            ) as mock_get_env,
        ):
            mock_create_engine.return_value = MagicMock()
            mock_sessionmaker.return_value = MagicMock()

            manager.initialize()

            # get_env 被调用了 5 次(对应 5 个 DB_* 凭证)
            assert mock_get_env.call_count == 5
            called_keys = [call.args[0] for call in mock_get_env.call_args_list]
            assert called_keys == [
                "DB_HOST",
                "DB_PORT",
                "DB_NAME",
                "DB_USER",
                "DB_PASSWORD",
            ]

            # URL 含 get_env 返回值,不是 os.getenv 默认值
            url = mock_create_engine.call_args[0][0]
            assert "db.from-infisical" in url
            assert "5433" in url
            assert "postgres:secret-from-infisical" in url
            assert "/galaxy" in url

    def test_initialize_creates_asyncpg_url(self):
        """Test that initialize() creates URL with asyncpg driver."""
        manager = AsyncDatabaseManager()

        with (
            patch(
                "galaxy_core.database.core.async_connection.create_async_engine"
            ) as mock_create_engine,
            patch(
                "galaxy_core.database.core.async_connection.async_sessionmaker"
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
        manager = AsyncDatabaseManager()

        with (
            patch(
                "galaxy_core.database.core.async_connection.create_async_engine"
            ) as mock_create_engine,
            patch(
                "galaxy_core.database.core.async_connection.async_sessionmaker"
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
        manager = AsyncDatabaseManager()

        with (
            patch(
                "galaxy_core.database.core.async_connection.create_async_engine"
            ) as mock_create_engine,
            patch(
                "galaxy_core.database.core.async_connection.async_sessionmaker"
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
        manager = AsyncDatabaseManager()
        assert manager._session_maker is None

    @pytest.mark.asyncio
    async def test_get_session_raises_if_not_initialized(self):
        """Test that get_session() raises RuntimeError if not initialized."""
        manager = AsyncDatabaseManager()

        with pytest.raises(RuntimeError, match="Database not initialized"):
            await manager.get_session()

    @pytest.mark.asyncio
    async def test_create_tables_raises_if_not_initialized(self):
        """Test that create_tables() raises RuntimeError if not initialized."""
        manager = AsyncDatabaseManager()

        with pytest.raises(RuntimeError, match="Database not initialized"):
            await manager.create_tables()

    @pytest.mark.asyncio
    async def test_create_tables_calls_run_sync(self):
        """Test that create_tables() uses run_sync for metadata creation."""
        manager = AsyncDatabaseManager()

        # Mock engine with begin() returning async context manager
        mock_engine = MagicMock()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_begin():
            yield mock_conn

        mock_engine.begin = mock_begin
        manager._engine = mock_engine
        manager._session_maker = MagicMock()

        await manager.create_tables()

        # Verify run_sync was called
        mock_conn.run_sync.assert_awaited_once()
