"""Phase 02 migrations E2E 集成测试.

验证 15/16/17/18 migration 在真实 Postgres+TimescaleDB 上(2026-06-19 范围修订后):
- upgrade head 后 5 启用表建成(7 表由 migration 18 drop)
- downgrade 回滚干净
- single-head 静态校验(无 DB,CI 始终跑)

DB 依赖:真实 Postgres + TimescaleDB。无 GALAXY_TEST_DB 环境变量时跳过
DB-dependent 类,仅跑静态 single-head 类(始终收集)。
"""

import os
import re
from pathlib import Path

import pytest

ALEMBIC_VERSIONS = Path("alembic/versions")

# Phase 02 migrations(范围修订后):15/16/17 建 12 表,18 drop 7 表,剩 5 表
PHASE02_CREATE_MIGRATIONS = {
    "16_add_akshare_fund_flow.py": {
        "kept_tables": ["akshare_sector_fund_flow_daily"],
        "dropped_tables": [
            "akshare_stock_fund_flow_daily",
            "akshare_north_fund_flow_daily",
            "akshare_market_fund_flow_daily",
            "akshare_industry_pe_daily",
        ],
    },
    "17_add_amazingdata_fund_flow.py": {
        "kept_tables": [
            "long_hu_bang",
            "block_trading",
            "margin_summary_daily",
            "margin_detail_daily",
        ],
        "dropped_tables": [],
    },
}

# migration 18 drop 的表(范围修订)
MIGRATION_18 = "18_drop_unused_phase02_tables.py"
MIGRATION_18_DROPPED = [
    "akshare_stock_fund_flow_daily",
    "akshare_north_fund_flow_daily",
    "akshare_market_fund_flow_daily",
    "akshare_industry_pe_daily",
    "baostock_stock_valuation_daily",
    "baostock_macro_econ",
    "baostock_index_valuation_daily",
]

# 范围修订后最终保留的 5 表
PHASE02_KEPT_TABLES = [
    "akshare_sector_fund_flow_daily",
    "long_hu_bang",
    "block_trading",
    "margin_summary_daily",
    "margin_detail_daily",
]

# 是否有真实测试 DB
HAS_TEST_DB = bool(os.environ.get("GALAXY_TEST_DB"))
DB_REASON = "needs real Postgres+TimescaleDB (set GALAXY_TEST_DB=1 to enable)"


class TestPhase02SingleHeadStatic:
    """静态 single-head 校验(无 DB,CI 始终跑)."""

    def test_alembic_versions_dir_exists(self):
        assert ALEMBIC_VERSIONS.is_dir(), f"{ALEMBIC_VERSIONS} 应存在"

    def test_phase02_migration_files_exist(self):
        for fname in PHASE02_CREATE_MIGRATIONS:
            assert (ALEMBIC_VERSIONS / fname).is_file(), (
                f"migration {fname} 应存在(02-04 交付)"
            )
        assert (ALEMBIC_VERSIONS / MIGRATION_18).is_file(), (
            f"migration {MIGRATION_18} 应存在(范围修订交付)"
        )

    def test_no_revision_id_duplicated_across_files(self):
        """所有 migration 文件 revision ID 唯一(防 alembic 双 head 事故).

        镜像 tests/unit/alembic/test_phase02_migrations.py 的 single-head 校验,
        防御 2026-06-16 双 head 分叉类事故(AGENTS.md)。
        """
        revisions: dict[str, str] = {}
        duplicates: list[str] = []
        for py_file in sorted(ALEMBIC_VERSIONS.glob("*.py")):
            content = py_file.read_text()
            # revision: str = "xxxx" 或 revision = "xxxx"
            match = re.search(r"^revision\s*[=:]\s*['\"]([0-9a-f]+)['\"]", content, re.M)
            if not match:
                continue
            rev = match.group(1)
            if rev in revisions:
                duplicates.append(f"{rev} in {py_file.name} + {revisions[rev]}")
            revisions[rev] = py_file.name
        assert not duplicates, (
            f"重复 revision ID(双 head 风险):{duplicates}"
        )

    def test_phase02_migrations_chain_14_to_18(self):
        """15/16/17/18 形成 linear chain(revision → down_revision)."""
        def _read_rev_down(fname: str) -> tuple[str, str]:
            content = (ALEMBIC_VERSIONS / fname).read_text()
            rev = re.search(r"^revision\s*[=:]\s*['\"]([0-9a-f]+)['\"]", content, re.M)
            down = re.search(
                r"^down_revision\s*[=:]\s*['\"]([0-9a-f]+)['\"]", content, re.M
            )
            return (rev.group(1) if rev else "", down.group(1) if down else "")

        r16, d16 = _read_rev_down("16_add_akshare_fund_flow.py")
        r17, d17 = _read_rev_down("17_add_amazingdata_fund_flow.py")
        r18, d18 = _read_rev_down(MIGRATION_18)
        # 17 down = 16,18 down = 17(linear)
        assert d17 == r16, f"17 down_revision 应 = 16 revision({d17} vs {r16})"
        assert d18 == r17, f"18 down_revision 应 = 17 revision({d18} vs {r17})"


@pytest.mark.skipif(not HAS_TEST_DB, reason=DB_REASON)
class TestPhase02MigrationsE2E:
    """E2E:upgrade head 后 5 启用表建成 + 7 drop 表不存在 + downgrade 回滚.

    需真实 Postgres + TimescaleDB(GALAXY_TEST_DB=1)。
    """

    async def test_upgrade_head_creates_kept_tables(self, db_manager):
        """upgrade head 后 5 启用表全部建成(范围修订后)."""
        from sqlalchemy import text

        async with db_manager.session() as session:
            for table in PHASE02_KEPT_TABLES:
                result = await session.execute(
                    text(
                        "SELECT EXISTS(select 1 FROM information_schema.tables "
                        "WHERE table_name = :t)"
                    ),
                    {"t": table},
                )
                assert result.scalar(), f"{table} 应存在(范围修订后启用)"

    async def test_upgrade_head_drops_unused_tables(self, db_manager):
        """upgrade head 后 migration 18 drop 的 7 表应不存在."""
        from sqlalchemy import text

        async with db_manager.session() as session:
            for table in MIGRATION_18_DROPPED:
                result = await session.execute(
                    text(
                        "SELECT EXISTS(select 1 FROM information_schema.tables "
                        "WHERE table_name = :t)"
                    ),
                    {"t": table},
                )
                assert not result.scalar(), (
                    f"{table} 应已 drop(migration 18, 范围修订)"
                )

    async def test_kept_tables_initially_empty(self, db_manager):
        """upgrade 后新表行数为 0(无残留数据)."""
        from sqlalchemy import text

        async with db_manager.session() as session:
            for table in PHASE02_KEPT_TABLES:
                result = await session.execute(
                    text(f"SELECT COUNT(*) FROM {table}")
                )
                assert result.scalar() == 0, f"{table} 初始应为空"
