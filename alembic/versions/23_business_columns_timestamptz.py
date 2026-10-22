"""business columns to timestamptz (table rebuild)

Revision ID: 23_biz_timestamptz
Revises: 22_drop_mv_symbol_completeness
Create Date: 2026-07-17 00:00:00.000000

把业务时间列 + 审计列从裸 `TIMESTAMP` / `DATE` 改为 `TIMESTAMPTZ`。

背景见 AGENTS.md 2026-07-17 审计:
SDK 返回北京时间字面值,程序未 attach tzinfo 直接存 `TIMESTAMP WITHOUT TIME ZONE`,
PG 不携带时区语义 → 业务列实际是北京 wall-clock 但裸列标记让消费方无任何线索。

## 为何用表重建而非 ALTER COLUMN TYPE

timescaledb 的 ALTER COLUMN TYPE 对 time dim 列有 chunk 约束障碍:
- naive 存量值 `2024-01-01 00:00:00`(北京 wall-clock)按 `AT TIME ZONE 'Asia/Shanghai'`
  解释成 timestamptz `2024-01-01 08:00:00+00`
- 但 chunk 边界约束(naive)被 timescaledb 按字面 UTC 解释成 `2024-01-01 00:00:00+00`
- 数据偏移 +8h 后跑出原 chunk 边界 → `CheckViolation`(实测 kline_day 1487 万行失败)

表重建方案规避此问题(用 CREATE TABLE LIKE 复制列定义,避免手写 schema 漂移):
1. RENAME 旧表 → 脱离 hypertable 关系(变普通表)
2. CREATE 新表 `(LIKE old)` → 复制所有列 + NOT NULL
3. ALTER 新表 time 列 + 审计列为 timestamptz
4. create_hypertable(new) → chunk 边界用 timestamptz 正确划分
5. INSERT INTO new SELECT 转换 FROM old → timescaledb 自动把每行归入正确 chunk
6. CREATE INDEX 重建 PK + 业务索引(从 pg_indexes 动态读取)
7. DROP TABLE old

## 数据转换语义

- 业务时间列(trade_time/trade_date/list_date/delist_date):naive 北京 wall-clock
  → timestamptz(按 Asia/Shanghai 解释),instant 对应北京 wall-clock 那一刻。
  例:naive `2024-01-01 00:00:00` → `2023-12-31 16:00:00+00`
  读出 `AT TIME ZONE 'Asia/Shanghai'` = `2024-01-01 00:00:00` 北京,无损。
- 审计列(created_at/updated_at):naive UTC wall-clock → timestamptz(按 UTC 解释)。

## 范围(用户选定 B)

- **kline 13 表** + **Date 列 hypertable 7 表**(backward_factor/industry_daily/
  4 fund_flow/akshare):表重建
- **trading_calendar**(普通表,PK=trade_date):表重建
- **stock_basic**(普通表,业务列 list_date/delist_date):直接 ALTER(无 chunk 约束)
- **审计列-only 5 表**(index_constituent/index_weight/industry_base_info/
  industry_constituent/industry_weight):直接 ALTER(业务时间是 String 不动)

**不动**:String(8) 列 8 表 + `last_sync_date.last_sync_date`(Date 语义「日期」非「时刻」)。

## 事务性

每个表的重建是独立 DDL+DML 序列。alembic 默认 transaction_per_migration=True,
整个 upgrade() 在单事务内。13 GB 的 backward_factor INSERT SELECT 在事务内可跑,
WAL 涨大但 PG 能扛。如生产环境内存/磁盘紧张,改用分批或裸 SQL 脚本。

downgrade 不可逆(timestamptz → naive 会丢失北京时间语义)。
"""
import re
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "23_biz_timestamptz"
down_revision: Union[str, Sequence[str], None] = "22_drop_mv_symbol_completeness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


KLINE_TABLES = [
    "kline_min1", "kline_min3", "kline_min5", "kline_min10", "kline_min15",
    "kline_min30", "kline_min60", "kline_min120", "kline_day", "kline_week",
    "kline_month", "kline_season", "kline_year",
]


def _get_indexes(bind, table: str) -> list[tuple[str, str, bool]]:
    """读旧表索引定义(用于在新表上重建).

    Returns:
        [(index_name, index_def_full_sql, is_unique)]
        index_def_full_sql 是 pg_indexes.indexdef 的值,如
        "CREATE UNIQUE INDEX foo_pkey ON public.foo USING btree (a, b)"
    """
    result = bind.execute(
        text(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = :t ORDER BY indexname;"
        ),
        {"t": table},
    )
    indexes = []
    for row in result:
        name, defn = row[0], row[1]
        is_unique = "UNIQUE" in defn.upper()
        indexes.append((name, defn, is_unique))
    return indexes


def _rebuild_hypertable(
    table: str,
    time_col: str,
    chunk_interval: str,
    biz_tz: str = "Asia/Shanghai",
) -> None:
    """通用 hypertable 表重建.

    流程(规避 timescaledb ALTER time dim 的 chunk 约束障碍 + 索引名冲突 +
    hypertable 不支持 ADD PRIMARY KEY USING INDEX 限制):

    1. RENAME old → legacy(legacy 的索引名不变,仍叫 <table>_pkey 等)
    2. CREATE new (LIKE legacy) 复制列定义 + NOT NULL
    3. ALTER new: time_col + created_at + updated_at → timestamptz
    4. 读 legacy 索引定义(存内存)
    5. DROP legacy(清掉同名索引,因 ALTER TABLE RENAME 不重命名索引)
    6. 在 new 上重建 PK(timescaledb 要求 PK 在 create_hypertable 前定义,
       且 PK 必须含 time_col)
    7. INSERT INTO new SELECT 转换 FROM ... —— 但 legacy 已删!
       改:步骤 4.5 把 legacy 数据先导出到 new,再 DROP legacy
    实际顺序调整为(见代码):
      rename → create new → alter types → 迁数据 → 读索引 → drop legacy →
      建 PK → create_hypertable(migrate_data=>true) → 建业务索引
    """
    bind = op.get_bind()
    legacy = f"{table}__legacy_23"

    # 1. rename
    op.execute(f"ALTER TABLE {table} RENAME TO {legacy};")
    # 2. create new (LIKE,含 NOT NULL,不含索引)
    op.execute(
        f"CREATE TABLE {table} (LIKE {legacy} INCLUDING DEFAULTS INCLUDING CONSTRAINTS);"
    )
    # 3. alter types: time_col(业务北京) + 审计列(UTC)
    op.execute(
        f"ALTER TABLE {table} ALTER COLUMN {time_col} "
        f"TYPE timestamptz USING {time_col}::timestamp AT TIME ZONE '{biz_tz}';"
    )
    op.execute(
        f"ALTER TABLE {table} ALTER COLUMN created_at "
        f"TYPE timestamptz USING created_at AT TIME ZONE 'UTC';"
    )
    op.execute(
        f"ALTER TABLE {table} ALTER COLUMN updated_at "
        f"TYPE timestamptz USING COALESCE(updated_at, created_at) AT TIME ZONE 'UTC';"
    )
    # 4. 迁数据(legacy → new,带时区转换)
    _migrate_data(table, legacy, time_col, biz_tz, bind)
    # 5. 读 legacy 索引定义(DROP 前读)
    indexes = _get_indexes(bind, legacy)
    # 6. DROP legacy(清同名索引,以便新表用同名建索引)
    op.execute(f"DROP TABLE {legacy};")
    # 7. 建 PK(timescaledb 要求 hypertable 的 PK 在 create_hypertable 前定义)
    _create_primary_key(table, indexes)
    # 8. create_hypertable(new, migrate_data => true):有数据转 hypertable,
    #    chunk 边界用 timestamptz 干净划分
    op.execute(
        f"SELECT create_hypertable('{table}', '{time_col}', "
        f"if_not_exists => true, migrate_data => true, "
        f"chunk_time_interval => {chunk_interval});"
    )
    # 9. 建业务索引(PK 已建,跳过;time dim 索引由 create_hypertable 自动建,跳过)
    _recreate_non_pk_indexes(table, indexes, time_col=time_col)


def _create_primary_key(
    table: str, indexes: list[tuple[str, str, bool]]
) -> None:
    """从 legacy 索引定义提取 PK 并在新表创建.

    hypertable 要求 PK 在 create_hypertable 前定义,故单独提前建。
    用 ADD PRIMARY KEY (cols) 而非 ADD PRIMARY KEY USING INDEX(hypertable 不支持后者)。
    """
    for name, defn, _is_unique in indexes:
        if not name.endswith("_pkey"):
            continue
        # defn 形如 "CREATE UNIQUE INDEX xxx_pkey ON public.<legacy> USING btree (a, b)"
        # 提取列定义
        match = re.search(r"USING btree \(([^)]+)\)", defn)
        if not match:
            continue
        cols = match.group(1)
        op.execute(f"ALTER TABLE {table} ADD PRIMARY KEY ({cols});")
        return


def _recreate_non_pk_indexes(
    table: str,
    indexes: list[tuple[str, str, bool]],
    time_col: str | None = None,
) -> None:
    """重建非 PK 业务索引.

    PK 已在 create_hypertable 前单独建。
    time_col 若给定,跳过 time dim 索引(create_hypertable 已自动建)。
    """
    legacy_qualified = f"public.{table}__legacy_23"
    new_qualified = f"public.{table}"
    for name, defn, _is_unique in indexes:
        if name.endswith("_pkey"):
            continue
        # 跳过 time dim 单列索引(create_hypertable 自动建,重建会冲突)
        if time_col:
            match = re.search(r"USING btree \(([^)]+)\)", defn)
            if match:
                idx_col = match.group(1).strip().split()[0]
                if idx_col == time_col:
                    continue
        new_defn = defn.replace(legacy_qualified, new_qualified)
        op.execute(new_defn)


def _migrate_data(
    new_tbl: str, legacy: str, time_col: str, biz_tz: str, bind
) -> None:
    """迁数据:time 列按 biz_tz 解释,created_at/updated_at 按 UTC 解释."""
    result = bind.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t ORDER BY ordinal_position;"
        ),
        {"t": legacy},
    )
    all_cols = [r[0] for r in result]

    select_exprs = []
    for col in all_cols:
        if col == time_col:
            select_exprs.append(f"{col}::timestamp AT TIME ZONE '{biz_tz}' AS {col}")
        elif col == "created_at":
            select_exprs.append(f"{col} AT TIME ZONE 'UTC' AS {col}")
        elif col == "updated_at":
            select_exprs.append(
                f"COALESCE({col}, created_at) AT TIME ZONE 'UTC' AS {col}"
            )
        else:
            select_exprs.append(col)
    col_list = ", ".join(all_cols)
    expr_list = ", ".join(select_exprs)
    op.execute(
        f"INSERT INTO {new_tbl} ({col_list}) SELECT {expr_list} FROM {legacy};"
    )


def _recreate_indexes_from_defs(
    new_tbl: str, indexes: list[tuple[str, str, bool]]
) -> None:
    """根据索引定义列表在新表重建索引.

    Args:
        new_tbl: 新表名
        indexes: [(index_name, index_def_full_sql, is_unique)] from _get_indexes
                 (在 legacy 表上读取,定义含 `public.<new_tbl>__legacy_23`)
    """
    legacy_qualified = f"public.{new_tbl}__legacy_23"
    new_qualified = f"public.{new_tbl}"
    for name, defn, _is_unique in indexes:
        # 把 defn 里的 legacy 表名替换为新表名
        new_defn = defn.replace(legacy_qualified, new_qualified)
        op.execute(new_defn)
        if name.endswith("_pkey"):
            op.execute(
                f"ALTER TABLE {new_tbl} ADD PRIMARY KEY USING INDEX {name};"
            )


def _rebuild_normal_table_date(
    table: str, biz_tz: str = "Asia/Shanghai"
) -> None:
    """重建普通表(非 hypertable)的 trade_date Date → timestamptz.

    用于 trading_calendar(无 hypertable 但 trade_date 是 PK,业务时间列)。
    """
    bind = op.get_bind()
    legacy = f"{table}__legacy_23"
    op.execute(f"ALTER TABLE {table} RENAME TO {legacy};")
    op.execute(
        f"CREATE TABLE {table} (LIKE {legacy} INCLUDING DEFAULTS INCLUDING CONSTRAINTS);"
    )
    op.execute(
        f"ALTER TABLE {table} ALTER COLUMN trade_date "
        f"TYPE timestamptz USING trade_date::timestamp AT TIME ZONE '{biz_tz}';"
    )
    # 审计列
    op.execute(
        f"ALTER TABLE {table} ALTER COLUMN created_at "
        f"TYPE timestamptz USING created_at AT TIME ZONE 'UTC';"
    )
    op.execute(
        f"ALTER TABLE {table} ALTER COLUMN updated_at "
        f"TYPE timestamptz USING COALESCE(updated_at, created_at) AT TIME ZONE 'UTC';"
    )
    _migrate_data(table, legacy, "trade_date", biz_tz, bind)
    indexes = _get_indexes(bind, legacy)
    op.execute(f"DROP TABLE {legacy};")
    _recreate_indexes_from_defs(table, indexes)


def upgrade() -> None:
    """业务/审计列 → timestamptz(表重建)."""

    # (1) kline 13 表(DateTime hypertable,默认 7 天 chunk)
    for tbl in KLINE_TABLES:
        _rebuild_hypertable(tbl, "trade_time", "INTERVAL '7 days'")

    # (2) Date 列 hypertable 表
    _rebuild_hypertable(
        "backward_factor", "trade_date", "INTERVAL '1 year'"
    )
    _rebuild_hypertable("industry_daily", "trade_date", "INTERVAL '1 month'")
    _rebuild_hypertable("long_hu_bang", "trade_date", "INTERVAL '1 month'")
    _rebuild_hypertable("block_trading", "trade_date", "INTERVAL '1 month'")
    _rebuild_hypertable(
        "margin_summary_daily", "trade_date", "INTERVAL '1 month'"
    )
    _rebuild_hypertable(
        "margin_detail_daily", "trade_date", "INTERVAL '1 month'"
    )
    _rebuild_hypertable(
        "akshare_sector_fund_flow_daily", "trade_date", "INTERVAL '1 month'"
    )

    # (3) 普通表 trading_calendar(非 hypertable)
    _rebuild_normal_table_date("trading_calendar")

    # (4) stock_basic(普通表,非 hypertable,直接 ALTER 无 chunk 约束问题)
    op.execute(
        "ALTER TABLE stock_basic ALTER COLUMN list_date "
        "TYPE timestamptz USING list_date::timestamp AT TIME ZONE 'Asia/Shanghai';"
    )
    op.execute(
        "ALTER TABLE stock_basic ALTER COLUMN delist_date "
        "TYPE timestamptz USING delist_date::timestamp AT TIME ZONE 'Asia/Shanghai';"
    )
    op.execute(
        "ALTER TABLE stock_basic ALTER COLUMN created_at "
        "TYPE timestamptz USING created_at AT TIME ZONE 'UTC';"
    )
    op.execute(
        "ALTER TABLE stock_basic ALTER COLUMN updated_at "
        "TYPE timestamptz USING COALESCE(updated_at, created_at) AT TIME ZONE 'UTC';"
    )

    # (5) 审计列-only 5 表(业务时间是 String 不动)
    for tbl in [
        "index_constituent",
        "index_weight",
        "industry_base_info",
        "industry_constituent",
        "industry_weight",
    ]:
        op.execute(
            f"ALTER TABLE {tbl} ALTER COLUMN created_at "
            f"TYPE timestamptz USING created_at AT TIME ZONE 'UTC';"
        )
        op.execute(
            f"ALTER TABLE {tbl} ALTER COLUMN updated_at "
            f"TYPE timestamptz USING COALESCE(updated_at, created_at) AT TIME ZONE 'UTC';"
        )


def downgrade() -> None:
    """不可逆。

    timestamptz → naive 会丢失北京时间语义。如需回滚需 pg_dump + 重建。
    """
    pass
