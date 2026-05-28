"""Async database connection management.

TimescaleDB connection pool and ORM session management using async SQLAlchemy.
Provides async engine and session context manager for async database operations.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from galaxy_db_sync.database.models import Base

logger = logging.getLogger(__name__)


class AsyncDatabaseManager:
    """Async database manager.

    Manages PostgreSQL connection pool and ORM sessions using async SQLAlchemy.
    """

    _instance = None
    _engine: AsyncEngine | None = None
    _session_maker: async_sessionmaker[AsyncSession] | None = None

    def __new__(cls) -> "AsyncDatabaseManager":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30,
        echo: bool = False,
    ) -> None:
        """Initialize async database connection pool.

        Args:
            host: Database host
            port: Database port
            database: Database name
            user: User name
            password: Password
            pool_size: Connection pool size
            max_overflow: Maximum overflow connections
            pool_timeout: Connection timeout (seconds)
            echo: Whether to print SQL statements
        """
        # Get configuration from environment variables or parameters
        host = host or os.getenv("DB_HOST", "localhost")
        port = port or int(os.getenv("DB_PORT", "5432"))
        database = database or os.getenv("DB_NAME", "quant_db")
        user = user or os.getenv("DB_USER", "quant_user")
        password = password or os.getenv("DB_PASSWORD", "")

        # Build connection URL with asyncpg driver
        database_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"

        self._engine = create_async_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,  # Verify connections before use
            echo=echo,
        )

        # Critical: expire_on_commit=False prevents DetachedInstanceError in async
        self._session_maker = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        logger.info(f"Async database connection pool initialized: {host}:{port}/{database}")

    async def create_tables(self) -> None:
        """Create all database tables asynchronously."""
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database tables created")

        # Create TimescaleDB hypertables via run_sync
        await self._create_hypertables_async()

    async def _create_hypertables_async(self) -> None:
        """Create TimescaleDB hypertables asynchronously via run_sync."""
        if self._engine is None:
            return

        async with self._engine.begin() as conn:
            await conn.run_sync(_create_hypertables_sync)

    async def drop_tables(self) -> None:
        """Drop all database tables (use with caution)."""
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        logger.info("Database tables dropped")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async session context manager.

        Yields:
            SQLAlchemy AsyncSession object

        Example:
            >>> async with async_db_manager.session() as session:
            ...     result = await session.execute(select(StockInfo))
        """
        if self._session_maker is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        session = self._session_maker()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            await session.close()

    async def get_session(self) -> AsyncSession:
        """Get a new async session.

        Returns:
            SQLAlchemy AsyncSession object

        Note:
            Must be closed manually with await session.close()
        """
        if self._session_maker is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._session_maker()

    async def close(self) -> None:
        """Close async database connection pool."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Async database connection pool closed")


def _create_hypertables_sync(sync_conn) -> None:
    """Sync helper for TimescaleDB hypertable creation.

    This function is called via run_sync from async context.
    """
    from sqlalchemy import text

    # Check TimescaleDB extension
    result = sync_conn.execute(
        text("SELECT installed_version FROM pg_available_extensions WHERE name = 'timescaledb'")
    )
    if not result.fetchone():
        logger.warning("TimescaleDB extension not installed, skipping hypertable creation")
        return

    kline_tables = [
        "kline_min1",
        "kline_min3",
        "kline_min5",
        "kline_min10",
        "kline_min15",
        "kline_min30",
        "kline_min60",
        "kline_min120",
        "kline_day",
        "kline_week",
        "kline_month",
        "kline_season",
        "kline_year",
    ]

    for table_name in kline_tables:
        try:
            sync_conn.execute(
                text(
                    f"SELECT create_hypertable('{table_name}', 'trade_time', if_not_exists => true)"
                )
            )
            logger.info(f"Hypertable created: {table_name}")
        except Exception as e:
            logger.warning(f"Failed to create hypertable {table_name}: {e}")


# Global async database manager instance
async_db_manager = AsyncDatabaseManager()


async def init_async_database(
    host: str | None = None,
    port: int | None = None,
    database: str | None = None,
    user: str | None = None,
    password: str | None = None,
    create_tables: bool = True,
) -> AsyncDatabaseManager:
    """Initialize async database and return manager.

    Args:
        host: Database host
        port: Database port
        database: Database name
        user: User name
        password: Password
        create_tables: Whether to auto-create tables

    Returns:
        AsyncDatabaseManager instance
    """
    async_db_manager.initialize(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    if create_tables:
        await async_db_manager.create_tables()

    return async_db_manager
