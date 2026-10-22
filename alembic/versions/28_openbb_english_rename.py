"""P1 表结构回迁 OpenBB/Grafana 形态(2026-09-28,NocoDB 适配作废).

三件事(见 .work/openbb-grafana/PLAN.md 决策表 D1/D2/D4/D7/D9):
1. D1:36 张业务表中文表名 → 英文 snake_case(= 回迁 nocodb 化之前旧名;
   数据原地,不重拉)。hypertable/约束/序列随 ALTER TABLE RENAME 自动跟随;
   中文命名的性能索引一并 ALTER INDEX RENAME(英文索引名本就正确的跳过)。
2. D2:删 NocoDB 系统列 created_by/updated_by/nc_order/nc_row_meta
   (保留 id——nixos-config 出站 upsert 用;created_at/updated_at——watermark 用)。
3. D4:security_type 多值串(`SH_A,EXTRA_STOCK_A,...`)回写单市场码
   (split_part 取首元素)——NocoDB MultiSelect 产物退场。
4. D7:枚举参考表 DROP(NocoDB 独有,代码不消费)。

幂等:全部经 to_regclass / information_schema 守卫,重复执行零操作。
Qnap 备库重建走 pg_dump/restore(本 migration 不在备库执行)。

Revision ID: 28_openbb_english_rename
Revises: 27_lhb_change_range_float8
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "28_openbb_english_rename"
down_revision: str | Sequence[str] | None = "27_lhb_change_range_float8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 中文表名 → 英文表名(枚举参考除外——直接 DROP)
RENAME: dict[str, str] = {
    "日线行情": "kline_day",
    "周线行情": "kline_week",
    "月线行情": "kline_month",
    "季线行情": "kline_season",
    "年线行情": "kline_year",
    "1分钟K线": "kline_min1",
    "3分钟K线": "kline_min3",
    "5分钟K线": "kline_min5",
    "10分钟K线": "kline_min10",
    "15分钟K线": "kline_min15",
    "30分钟K线": "kline_min30",
    "60分钟K线": "kline_min60",
    "120分钟K线": "kline_min120",
    "交易日历": "trading_calendar",
    "证券基本信息": "stock_basic",
    "复权因子": "backward_factor",
    "指数成分股": "index_constituent",
    "指数权重": "index_weight",
    "行业基本信息": "industry_base_info",
    "行业成分股": "industry_constituent",
    "行业日行情": "industry_daily",
    "行业权重": "industry_weight",
    "龙虎榜": "long_hu_bang",
    "大宗交易": "block_trading",
    "两融明细": "margin_detail_daily",
    "两融汇总": "margin_summary_daily",
    "板块资金流": "akshare_sector_fund_flow_daily",
    "资产负债表": "balance_sheet",
    "现金流量表": "cash_flow",
    "利润表": "income",
    "业绩快报": "profit_express",
    "业绩预告": "profit_notice",
    "分红配送": "dividend",
    "最后同步日期": "last_sync_date",
    "同步状态": "sync_state",
}

# 中文索引名 → 英文索引名(改名表对应;英文已正确的在 TASKS 名单外自动跳过)
RENAME_INDEX: dict[str, str] = {
    "日线行情_trade_time_idx": "kline_day_trade_time_idx",
    "周线行情_trade_time_idx": "kline_week_trade_time_idx",
    "月线行情_trade_time_idx": "kline_month_trade_time_idx",
    "季线行情_trade_time_idx": "kline_season_trade_time_idx",
    "年线行情_trade_time_idx": "kline_year_trade_time_idx",
    "1分钟K线_trade_time_idx": "kline_min1_trade_time_idx",
    "3分钟K线_trade_time_idx": "kline_min3_trade_time_idx",
    "5分钟K线_trade_time_idx": "kline_min5_trade_time_idx",
    "10分钟K线_trade_time_idx": "kline_min10_trade_time_idx",
    "15分钟K线_trade_time_idx": "kline_min15_trade_time_idx",
    "30分钟K线_trade_time_idx": "kline_min30_trade_time_idx",
    "60分钟K线_trade_time_idx": "kline_min60_trade_time_idx",
    "120分钟K线_trade_time_idx": "kline_min120_trade_time_idx",
    "复权因子_trade_date_idx": "backward_factor_trade_date_idx",
    "龙虎榜_trade_date_idx": "long_hu_bang_trade_date_idx",
    "大宗交易_trade_date_idx": "block_trading_trade_date_idx",
    "两融明细_trade_date_idx": "margin_detail_daily_trade_date_idx",
    "行业日行情_trade_date_idx": "industry_daily_trade_date_idx",
    "板块资金流_trade_date_idx": "akshare_sector_fund_flow_daily_trade_date_idx",
    "指数权重_trade_date_idx": "index_weight_trade_date_idx",
    "行业权重_trade_date_idx": "industry_weight_trade_date_idx",
}

DROP_SYSTEM_COLUMNS = ("created_by", "updated_by", "nc_order", "nc_row_meta")


def _table_exists(tbl: str) -> str:
    return f"to_regclass('public.\"{tbl}\"') IS NOT NULL"


def _column_exists(tbl: str, col: str) -> str:
    return (
        f"EXISTS (SELECT 1 FROM information_schema.columns "
        f"WHERE table_schema='public' AND table_name='{tbl}' AND column_name='{col}')"
    )


def _index_exists(idx: str) -> str:
    return f"EXISTS (SELECT 1 FROM pg_class WHERE relname='{idx}' AND relkind='i')"


def upgrade() -> None:
    # 1) D4 先行:security_type 多值串 → 单市场码(改名前后皆可,放最前批量一次)
    for tbl in RENAME:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF {_table_exists(tbl)} AND {_column_exists(tbl, "security_type")} THEN
                    UPDATE public."{tbl}"
                    SET security_type = split_part(security_type, ',', 1)
                    WHERE security_type LIKE '%,%';
                END IF;
            END $$;
            """
        )

    # 2) D2:删系统列(逐表守卫)
    for tbl in RENAME:
        cols = ", ".join(f"DROP COLUMN IF EXISTS {c}" for c in DROP_SYSTEM_COLUMNS)
        op.execute(
            f"""
            DO $$
            BEGIN
                IF {_table_exists(tbl)} THEN
                    EXECUTE 'ALTER TABLE public."{tbl}" {cols}';
                END IF;
            END $$;
            """
        )

    # 3) D7:枚举参考表 DROP(NocoDB 独有)
    op.execute('DROP TABLE IF EXISTS public."枚举参考"')

    # 4) D1:中文索引改名(先于表改名,避免同名冲突混淆)
    for old_idx, new_idx in RENAME_INDEX.items():
        op.execute(
            f"""
            DO $$
            BEGIN
                IF {_index_exists(old_idx)} AND NOT {_index_exists(new_idx)} THEN
                    EXECUTE 'ALTER INDEX public."{old_idx}" RENAME TO "{new_idx}"';
                END IF;
            END $$;
            """
        )

    # 5) D1:表改名(hypertable/约束/序列跟随)
    for old_tbl, new_tbl in RENAME.items():
        op.execute(
            f"""
            DO $$
            BEGIN
                IF {_table_exists(old_tbl)} THEN
                    EXECUTE 'ALTER TABLE public."{old_tbl}" RENAME TO "{new_tbl}"';
                END IF;
            END $$;
            """
        )


def downgrade() -> None:
    # 反向:英文 → 中文(仅表名与索引;系统列/多值串不还原——信息已删,downgrade 只保结构可回溯)
    for new_tbl, old_tbl in RENAME.items():
        op.execute(
            f"""
            DO $$
            BEGIN
                IF {_table_exists(new_tbl)} AND NOT {_table_exists(old_tbl)} THEN
                    EXECUTE 'ALTER TABLE public."{new_tbl}" RENAME TO "{old_tbl}"';
                END IF;
            END $$;
            """
        )
    for new_idx, old_idx in RENAME_INDEX.items():
        op.execute(
            f"""
            DO $$
            BEGIN
                IF {_index_exists(new_idx)} AND NOT {_index_exists(old_idx)} THEN
                    EXECUTE 'ALTER INDEX public."{new_idx}" RENAME TO "{old_idx}"';
                END IF;
            END $$;
            """
        )
