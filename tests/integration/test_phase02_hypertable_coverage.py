"""Phase 02 hypertable 覆盖率集成测试.

验证 5 张 Phase 02 表全部建成 TimescaleDB hypertable(2026-06-19 范围修订后):
- akshare 1(akshare_sector_fund_flow_daily, trade_date)
- amazingdata 4(全 trade_date)

DB 依赖:真实 Postgres + TimescaleDB。无 GALAXY_TEST_DB 跳过。

注:范围修订删 7 表(baostock 3 + akshare 4), 由 migration 18 drop。
"""

import os
from pathlib import Path

import pytest

HAS_TEST_DB = bool(os.environ.get("GALAXY_TEST_DB"))
DB_REASON = "needs real Postgres+TimescaleDB (set GALAXY_TEST_DB=1 to enable)"

# Phase 02 5 表 → 预期 time_column(范围修订后, timescale.py 定义)
PHASE02_HYPERTABLES = {
    # akshare 1
    "akshare_sector_fund_flow_daily": "trade_date",
    # amazingdata 4
    "long_hu_bang": "trade_date",
    "block_trading": "trade_date",
    "margin_summary_daily": "trade_date",
    "margin_detail_daily": "trade_date",
}


class TestHypertableRegistrationStatic:
    """静态校验:timescale.py 注册 5 张 Phase 02 表(无 DB)."""

    def test_timescale_py_registers_all_5_tables(self):
        """create_kline_hypertables 注册全部 5 张 Phase 02 表(范围修订后)."""
        src = Path(
            "data/src/galaxy_core/database/core/timescale.py"
        ).read_text()
        for table in PHASE02_HYPERTABLES:
            assert f'"{table}"' in src or f"'{table}'" in src or table in src, (
                f"timescale.py 应注册 {table} 为 hypertable"
            )

    def test_timescale_py_does_not_register_dropped_tables(self):
        """范围修订回归:timescale.py 不应再注册已 drop 的 7 表."""
        src = Path(
            "data/src/galaxy_core/database/core/timescale.py"
        ).read_text()
        for dropped in [
            "baostock_stock_valuation_daily",
            "baostock_macro_econ",
            "baostock_index_valuation_daily",
            "akshare_stock_fund_flow_daily",
            "akshare_north_fund_flow_daily",
            "akshare_market_fund_flow_daily",
            "akshare_industry_pe_daily",
        ]:
            # 注册形式如 create_hypertable(session, "table_name"...)
            assert f'"{dropped}"' not in src and f"'{dropped}'" not in src, (
                f"timescale.py 不应再注册 {dropped}(已 drop)"
            )


@pytest.mark.skipif(not HAS_TEST_DB, reason=DB_REASON)
class TestHypertableCoverageE2E:
    """E2E:5 表全部是 hypertable.

    需真实 Postgres + TimescaleDB。
    """

    async def test_all_phase02_tables_are_hypertables(self, db_manager):
        """5 张 Phase 02 表全部在 timescaledb_information.hypertables."""
        from sqlalchemy import text

        async with db_manager.session() as session:
            result = await session.execute(
                text(
                    "SELECT hypertable_name FROM timescaledb_information.hypertables"
                )
            )
            hypertables = {r[0] for r in result}
            for table in PHASE02_HYPERTABLES:
                assert table in hypertables, (
                    f"{table} 应是 hypertable(实际 hypertables: {sorted(hypertables)[:5]}...)"
                )

    async def test_hypertable_count_matches(self, db_manager):
        """Phase 02 hypertable 数 = 5(1+4, 范围修订后)."""
        from sqlalchemy import text

        async with db_manager.session() as session:
            result = await session.execute(
                text(
                    "SELECT COUNT(*) FROM timescaledb_information.hypertables "
                    "WHERE hypertable_name = ANY(:tables)"
                ),
                {"tables": list(PHASE02_HYPERTABLES.keys())},
            )
            assert result.scalar() == 5, "应有 5 张 Phase 02 hypertable(范围修订后)"
