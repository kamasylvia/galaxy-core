"""nocodb 形态补齐:20 张 hypertable 业务主键 + 全表审计时间默认值(2026-08-26).

背景(nixos-config 出站同步实测暴露,见 TODO 观察期新发现):
1. 25_nocodb_baseline 回迁时,hypertable 转换(drop PK(id),不含分区列)
   导致 20 张时间序列表无主键 → 出站 upsert 增量对这批表跳过。
   修复:业务复合键全部含分区列(trade_time/trade_date),直接
   `ADD PRIMARY KEY USING INDEX <既有 uq 索引>` —— 复用已建唯一索引,
   不重扫大表(1.1 亿行复权因子秒级),约束名沿用 uq_* 索引名。
2. 写路径不维护 created_at/updated_at(D2 决策"应用不写"),新插入行
   两列恒 NULL → 出站增量 watermark 失效。修复:DB 层
   `SET DEFAULT now()`(应用 INSERT 省略列时自动填,now() 经会话
   TimeZone=Asia/Shanghai 转 naive 北京时间);冲突更新分支由应用层
   upsert set_ 显式 updated_at=func.now() 补(companion 代码改动)。

Revision ID: 26_business_pk_defaults
Revises: 25_nocodb_baseline
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "26_business_pk_defaults"
down_revision: str | Sequence[str] | None = "25_nocodb_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 表 → (既有 uq 约束名, 业务主键列)。ADD PRIMARY KEY USING INDEX 被
# "index already associated with a constraint" 挡(uq 是约束不是裸索引),
# 改为 DROP CONSTRAINT 后 ADD PRIMARY KEY(重建索引,大表耗几分钟)。
PK_TABLES: dict[tuple[str, str], tuple[str, ...]] = {
    ("日线行情", "uq_kline_day_symbol_trade_time"): ("symbol", "trade_time"),
    ("周线行情", "uq_kline_week_symbol_trade_time"): ("symbol", "trade_time"),
    ("月线行情", "uq_kline_month_symbol_trade_time"): ("symbol", "trade_time"),
    ("季线行情", "uq_kline_season_symbol_trade_time"): ("symbol", "trade_time"),
    ("年线行情", "uq_kline_year_symbol_trade_time"): ("symbol", "trade_time"),
    ("1分钟K线", "uq_kline_min1_symbol_trade_time"): ("symbol", "trade_time"),
    ("3分钟K线", "uq_kline_min3_symbol_trade_time"): ("symbol", "trade_time"),
    ("5分钟K线", "uq_kline_min5_symbol_trade_time"): ("symbol", "trade_time"),
    ("10分钟K线", "uq_kline_min10_symbol_trade_time"): ("symbol", "trade_time"),
    ("15分钟K线", "uq_kline_min15_symbol_trade_time"): ("symbol", "trade_time"),
    ("30分钟K线", "uq_kline_min30_symbol_trade_time"): ("symbol", "trade_time"),
    ("60分钟K线", "uq_kline_min60_symbol_trade_time"): ("symbol", "trade_time"),
    ("120分钟K线", "uq_kline_min120_symbol_trade_time"): ("symbol", "trade_time"),
    ("复权因子", "uq_backward_factor_symbol_trade_date"): ("symbol", "trade_date"),
    ("板块资金流", "uq_akshare_3cols"): ("trade_date", "sector_type", "sector_name"),
    ("大宗交易", "uq_block_trading_4cols"): (
        "market_code",
        "trade_date",
        "b_buyer_name",
        "b_seller_name",
    ),
    ("行业日行情", "uq_industry_daily_code_trade_date"): ("index_code", "trade_date"),
    ("龙虎榜", "uq_lhb_4cols"): ("market_code", "trade_date", "trader_name", "flow_mark"),
    ("两融明细", "uq_margin_detail_code_trade_date"): ("market_code", "trade_date"),
    ("两融汇总", "uq_margin_summary_trade_date"): ("trade_date",),
}
PK_USING_INDEX = dict(PK_TABLES)  # downgrade 用

# 所有目标表(created_at/updated_at 默认值覆盖全部 public 业务表)
_TABLES_ALL = [tbl for (tbl, _uq) in PK_TABLES] + [
    "交易日历",
    "证券基本信息",
    "指数成分股",
    "指数权重",
    "行业基本信息",
    "行业成分股",
    "行业权重",
    "两融汇总",
    "资产负债表",
    "现金流量表",
    "利润表",
    "业绩快报",
    "业绩预告",
    "分红配送",
    "最后同步日期",
    "同步状态",
    "枚举参考",
]
_TABLES_ALL = sorted(set(_TABLES_ALL))


def _has_pk(tbl: str) -> str:
    return f"""
        EXISTS (
            SELECT 1 FROM pg_constraint c
            JOIN pg_class r ON c.conrelid = r.oid
            JOIN pg_namespace n ON r.relnamespace = n.oid
            WHERE n.nspname = 'public' AND r.relname = '{tbl}' AND c.contype = 'p'
        )
    """


def upgrade() -> None:
    # 1) 业务主键:drop 同列 uq 约束后 ADD PRIMARY KEY(列含分区列,hypertable 合法)
    for (tbl, uq), cols in PK_TABLES.items():
        col_list = ", ".join(f'"{c}"' for c in cols)
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT ({_has_pk(tbl)}) THEN
                    EXECUTE 'ALTER TABLE public."{tbl}" DROP CONSTRAINT IF EXISTS "{uq}"';
                    EXECUTE 'ALTER TABLE public."{tbl}" ADD CONSTRAINT "{uq}" '
                            'PRIMARY KEY ({col_list})';
                END IF;
            END $$;
            """
        )

    # 2) 审计时间默认值:INSERT 省略列时自动填 now()(会话 tz 转 naive 北京时间)
    for tbl in _TABLES_ALL:
        for col in ("created_at", "updated_at"):
            op.execute(
                f"""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = '{tbl}' AND column_name = '{col}'
                    ) THEN
                        EXECUTE 'ALTER TABLE public."{tbl}" '
                                'ALTER COLUMN {col} SET DEFAULT now()';
                    END IF;
                END $$;
                """
            )


def downgrade() -> None:
    for tbl, idx in PK_USING_INDEX.items():
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint c
                    JOIN pg_class r ON c.conrelid = r.oid
                    JOIN pg_namespace n ON r.relnamespace = n.oid
                    WHERE n.nspname = 'public' AND r.relname = '{tbl}'
                      AND c.contype = 'p' AND c.conname = '{idx}'
                ) THEN
                    EXECUTE 'ALTER TABLE public."{tbl}" DROP CONSTRAINT "{idx}"';
                END IF;
            END $$;
            """
        )
    for tbl in _TABLES_ALL:
        for col in ("created_at", "updated_at"):
            op.execute(
                f"""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = '{tbl}' AND column_name = '{col}'
                    ) THEN
                        EXECUTE 'ALTER TABLE public."{tbl}" '
                                'ALTER COLUMN {col} DROP DEFAULT';
                    END IF;
                END $$;
                """
            )
