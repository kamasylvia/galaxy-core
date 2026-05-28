"""数据库连接管理.

TimescaleDB 连接池和 ORM 会话管理.
TimescaleDB 是基于 PostgreSQL 的时间序列数据库，适用于存储 K 线等时间序列数据.
"""

import logging
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from galaxy_db_sync.database.models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器.

    负责管理 PostgreSQL 连接池和 ORM 会话.
    """

    _instance = None
    _engine = None
    _session_maker = None

    def __new__(cls) -> "DatabaseManager":
        """单例模式."""
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
        """初始化数据库连接池.

        Args:
            host: 数据库主机
            port: 数据库端口
            database: 数据库名
            user: 用户名
            password: 密码
            pool_size: 连接池大小
            max_overflow: 最大溢出连接数
            pool_timeout: 连接超时时间 (秒)
            echo: 是否打印 SQL 语句
        """
        # 从环境变量或参数获取配置
        host = host or os.getenv("DB_HOST", "localhost")
        port = port or int(os.getenv("DB_PORT", "5432"))
        database = database or os.getenv("DB_NAME", "quant_db")
        user = user or os.getenv("DB_USER", "quant_user")
        password = password or os.getenv("DB_PASSWORD", "")

        # 构建连接字符串
        database_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"

        self._engine = create_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,  # 检查连接是否有效
            echo=echo,
        )

        self._session_maker = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self._engine,
        )

        logger.info(f"数据库连接池初始化完成: {host}:{port}/{database}")

    def create_tables(self) -> None:
        """创建所有数据表."""
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call initialize () first.")

        Base.metadata.create_all(bind=self._engine)
        logger.info("数据表创建完成")

        # 为 K 线表创建 TimescaleDB hypertables
        # 注意：同步 DatabaseManager 不再自动创建 hypertables，
        # 请使用 AsyncDatabaseManager.create_tables() 或手动调用异步版本
        logger.info("同步 create_tables 跳过 hypertable 创建，请使用异步版本")

    def drop_tables(self) -> None:
        """删除所有数据表（慎用）."""
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call initialize () first.")

        Base.metadata.drop_all(bind=self._engine)
        logger.info("数据表删除完成")

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """获取数据库会话上下文管理器.

        Yields:
            SQLAlchemy Session 对象

        Example:
            >>> with db_manager.session () as session:
            ...     result = session.query (StockInfo).all ()
        """
        if self._session_maker is None:
            raise RuntimeError("Database not initialized. Call initialize () first.")

        session = self._session_maker()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            session.close()

    def get_session(self) -> Session:
        """获取一个新的数据库会话.

        Returns:
            SQLAlchemy Session 对象

        Note:
            使用完毕后需要手动关闭 session.close ()
        """
        if self._session_maker is None:
            raise RuntimeError("Database not initialized. Call initialize () first.")
        return self._session_maker()

    def close(self) -> None:
        """关闭数据库连接池."""
        if self._engine:
            self._engine.dispose()
            logger.info("数据库连接池已关闭")


# 全球数据库管理器实例
db_manager = DatabaseManager()


def init_database(
    host: str | None = None,
    port: int | None = None,
    database: str | None = None,
    user: str | None = None,
    password: str | None = None,
    create_tables: bool = True,
) -> DatabaseManager:
    """初始化数据库并返回管理器.

    Args:
        host: 数据库主机
        port: 数据库端口
        database: 数据库名
        user: 用户名
        password: 密码
        create_tables: 是否自动创建表

    Returns:
        DatabaseManager 实例
    """
    db_manager.initialize(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    if create_tables:
        db_manager.create_tables()

    return db_manager
