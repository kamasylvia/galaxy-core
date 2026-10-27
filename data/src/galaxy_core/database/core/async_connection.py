"""异步数据库连接管理。

使用 async SQLAlchemy 管理 TimescaleDB 连接池和 ORM 会话。
提供异步引擎和会话上下文管理器，用于异步数据库操作。
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

from galaxy_core.database.models import Base
from galaxy_core.shared_kernel.utils.infisical_config import get_env

logger = logging.getLogger(__name__)


class AsyncDatabaseManager:
    """异步数据库管理器。

    使用 async SQLAlchemy 管理 PostgreSQL 连接池和 ORM 会话。
    生命周期由 DI 容器管理（providers.Singleton）。
    """

    def __init__(self) -> None:
        """初始化（延迟加载）。"""
        self._engine: AsyncEngine | None = None
        self._session_maker: async_sessionmaker[AsyncSession] | None = None

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
        """初始化异步数据库连接池。

        Args:
            host: 数据库主机
            port: 数据库端口
            database: 数据库名称
            user: 用户名
            password: 密码
            pool_size: 连接池大小
            max_overflow: 最大溢出连接数
            pool_timeout: 连接超时（秒）
            echo: 是否打印 SQL 语句
        """
        # 防重复初始化
        if self._engine is not None:
            return

        # 从环境变量或参数获取配置（统一走 get_env：优先 Infisical，其次 os.environ）
        infisical_env = os.getenv("INFISICAL_ENVIRONMENT", "dev")
        host = host or get_env("DB_HOST", "localhost", environment=infisical_env)
        port_str = get_env("DB_PORT", "5432", environment=infisical_env)
        port = port or int(port_str or "5432")
        database = database or get_env("DB_NAME", "quant_db", environment=infisical_env)
        user = user or get_env("DB_USER", "quant_user", environment=infisical_env)
        password = password or get_env("DB_PASSWORD", "", environment=infisical_env)

        # 使用 asyncpg 驱动构建连接 URL
        database_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"

        self._engine = create_async_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,  # 使用前验证连接
            echo=echo,
            # 强制 session 时区为北京时间(2026-07-17 timestamptz 改造):
            # 业务时间列存的是北京 wall-clock 的 instant,session tz=Asia/Shanghai
            # 让读出的 aware datetime 直接显示为北京 wall-clock(.date() 即北京日期)。
            # 不设的话默认是 GMT,北京 00:00 的数据读出显示为 UTC 前一天 16:00。
            connect_args={"server_settings": {"TimeZone": "Asia/Shanghai"}},
        )

        # 关键：expire_on_commit=False 防止异步操作中的 DetachedInstanceError
        self._session_maker = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        logger.info(f"异步数据库连接池初始化完成: {host}:{port}/{database}")

    async def create_tables(self) -> None:
        """异步创建所有数据库表。

        警告：此方法使用 Base.metadata.create_all()，仅用于测试环境。
        生产环境请使用 Alembic 迁移（galaxy-core init-db）。
        """
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("数据库表创建完成")
        # 注意：生产环境的 hypertable 由 Alembic 迁移创建。
        # 测试环境如需 hypertable，请单独调用 create_kline_hypertables()。

    async def drop_tables(self) -> None:
        """删除所有数据库表（谨慎使用）。"""
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        logger.info("数据库表已删除")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取异步会话上下文管理器。

        Yields:
            SQLAlchemy AsyncSession 对象

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
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            await session.close()

    async def get_session(self) -> AsyncSession:
        """获取新的异步会话。

        Returns:
            SQLAlchemy AsyncSession 对象

        Note:
            必须手动关闭：await session.close()
        """
        if self._session_maker is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._session_maker()

    async def close(self) -> None:
        """关闭异步数据库连接池。"""
        if self._engine:
            await self._engine.dispose()
            logger.info("异步数据库连接池已关闭")
