"""nocodb 化回迁 baseline(2026-08-26).

本地 galaxy 库已整库重建为 nocodb 形态(见 docs/nocodb-reimport.md):
- 表名 = nocodb 中文表名(35 业务表 + 枚举参考)
- 业务时间列 = date(长 K trade_time / trade_date / reporting_period 等),
  分钟 K trade_time = naive timestamp
- NocoDB 系统列 id(serial PK)/created_at/updated_at/created_by/updated_by/
  nc_order/nc_row_meta
- 20 张 hypertable(分区参数复刻旧库)+ 业务唯一约束 uq_* + 性能索引

结构由 qnap nocodb 库 pg_dump 回拷建立,**不由本 migration 链生成**;
本文件为文档性 baseline:`alembic stamp head` 到此版本 = 声明 DB 处于
nocodb 形态。全新建库走回迁管道或 init-db(models 建表 + hypertable),
alembic upgrade 不再生成/修改业务表结构。

Revision ID: 25_nocodb_baseline
Revises: 24_audit_timestamptz
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "25_nocodb_baseline"
down_revision: Union[str, Sequence[str], None] = "24_audit_timestamptz"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """no-op:结构由回迁管道(pg_dump 回拷)建立,见模块 docstring."""
    pass


def downgrade() -> None:
    """no-op:回滚 = 恢复旧库备份(qnap galaxy 备份/P0 dump),非 DDL 可逆."""
    pass
