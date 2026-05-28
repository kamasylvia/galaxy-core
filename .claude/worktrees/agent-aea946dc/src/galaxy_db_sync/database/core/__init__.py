"""数据库访问层.

提供 TimescaleDB 连接池和 ORM 会话管理.
"""

from .connection import DatabaseManager, db_manager, init_database
from .timescale import create_hypertable, create_kline_hypertables

__all__ = [
    "DatabaseManager",
    "db_manager",
    "init_database",
    "create_hypertable",
    "create_kline_hypertables",
]
