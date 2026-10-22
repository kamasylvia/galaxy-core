"""Phase 02 Alembic migration 文件结构静态测试.

纯静态校验(读 migration 源码),不触 DB、不调 alembic CLI。
覆盖:revision/down_revision 头部 / 链线性无分叉 / has_table 幂等 / 表数匹配。
单 head 防护(AGENTS.md 2026-06-16 P0 双 head 事故回归)。
"""

import re
from pathlib import Path

import pytest

ALEMBIC_VERSIONS = Path(__file__).resolve().parents[3] / "alembic" / "versions"

MIGRATION_15 = ALEMBIC_VERSIONS / "15_add_baostock_data.py"
MIGRATION_16 = ALEMBIC_VERSIONS / "16_add_akshare_fund_flow.py"
MIGRATION_17 = ALEMBIC_VERSIONS / "17_add_amazingdata_fund_flow.py"


def _read(path: Path) -> str:
    """读 migration 文件源码."""
    return path.read_text(encoding="utf-8")


class TestPhase02MigrationStructure:
    """3 个 migration 文件头部 + 链线性 + 幂等守卫."""

    def test_migration_15_revision_and_down_revision(self):
        src = _read(MIGRATION_15)
        assert "revision: str = '15_add_baostock_data'" in src
        # down_revision 带 Union 类型注解(镜像 14 模板),用 substring 匹配
        assert "down_revision" in src and "'14_add_index_data'" in src

    def test_migration_16_revision_and_down_revision(self):
        src = _read(MIGRATION_16)
        assert "revision: str = '16_add_akshare_fund_flow'" in src
        assert "down_revision" in src and "'15_add_baostock_data'" in src

    def test_migration_17_revision_and_down_revision(self):
        src = _read(MIGRATION_17)
        assert "revision: str = '17_add_amazingdata_fund_flow'" in src
        assert "down_revision" in src and "'16_add_akshare_fund_flow'" in src

    def test_chain_linear_no_fork(self):
        """链线性:15.down=14, 16.down=15, 17.down=16,无分叉(AGENTS.md 双 head P0 防护).

        down_revision 注解是 Union[str, Sequence[str], None](镜像 14 模板),
        但实际赋值必须是单 str(非 list/tuple 多元)。
        """
        src15 = _read(MIGRATION_15)
        src16 = _read(MIGRATION_16)
        src17 = _read(MIGRATION_17)
        assert "'14_add_index_data'" in src15
        assert "'15_add_baostock_data'" in src16
        assert "'16_add_akshare_fund_flow'" in src17
        # 链线性:每个 down_revision 赋值是单 str(非 list/tuple)
        for src, rev in [
            (src15, "15_add_baostock_data"),
            (src16, "16_add_akshare_fund_flow"),
            (src17, "17_add_amazingdata_fund_flow"),
        ]:
            match = re.search(
                r"down_revision\s*(?::[^=]+)?=\s*(.+)$",
                src,
                re.MULTILINE,
            )
            assert match, f"{rev}: down_revision 行未找到"
            value = match.group(1).strip()
            # 赋值是单 str 引号字面量,非 [...]/(...) 多元
            assert not value.startswith("["), f"{rev}: down_revision 是 list(多元 fork)"
            assert not value.startswith("("), f"{rev}: down_revision 是 tuple(多元 fork)"

    @pytest.mark.parametrize(
        "path,expected_count",
        [
            (MIGRATION_15, 3),
            (MIGRATION_16, 5),
            (MIGRATION_17, 4),
        ],
    )
    def test_idempotency_guards(self, path, expected_count):
        """每 migration 的 has_table 守卫数 == 表数(3/5/4)."""
        src = _read(path)
        actual = src.count("if not inspector.has_table")
        assert actual == expected_count, f"{path.name}: has_table {actual} != {expected_count}"

    @pytest.mark.parametrize(
        "path,expected_min",
        [
            (MIGRATION_15, 3),
            (MIGRATION_16, 5),
            (MIGRATION_17, 4),
        ],
    )
    def test_date_columns_use_sa_date(self, path, expected_min):
        """所有 trade_date/date 列用 sa.Date()(非 String(8) 歧义)."""
        src = _read(path)
        actual = src.count("sa.Date()")
        assert actual >= expected_min, f"{path.name}: sa.Date() {actual} < {expected_min}"

    @pytest.mark.parametrize(
        "path,expected_count",
        [
            (MIGRATION_15, 3),
            (MIGRATION_16, 5),
            (MIGRATION_17, 4),
        ],
    )
    def test_drop_table_count(self, path, expected_count):
        """downgrade drop_table 数 == 表数(反序)."""
        src = _read(path)
        actual = src.count("op.drop_table")
        assert actual == expected_count

    def test_macro_uses_date_column_not_trade_date(self):
        """deviation 02-01:baostock_macro_econ 用 date 列(非 trade_date)."""
        src = _read(MIGRATION_15)
        assert "'date', sa.Date()" in src or "sa.Column('date', sa.Date()" in src
        # macro 表不应有 trade_date 列
        macro_block = re.search(
            r"has_table\('baostock_macro_econ'\).*?create_table\((.*?)\n        \)",
            src,
            re.DOTALL,
        )
        assert macro_block is not None
        assert "trade_date" not in macro_block.group(0)

    def test_macro_no_cpi_ppi_gdp(self):
        """deviation 02-01:macro 表无 CPI/PPI/GDP 列(SDK 无源)."""
        src = _read(MIGRATION_15)
        macro_block = re.search(
            r"has_table\('baostock_macro_econ'\).*?create_table\((.*?)\n        \)",
            src,
            re.DOTALL,
        )
        assert macro_block is not None
        block = macro_block.group(0).lower()
        assert "'cpi'" not in block
        assert "'ppi'" not in block
        assert "'gdp'" not in block

    def test_macro_has_loan_rate_and_reserve_ratio(self):
        """deviation 02-01:macro 表含 loan_rate_1y + reserve_ratio 列."""
        src = _read(MIGRATION_15)
        macro_block = re.search(
            r"has_table\('baostock_macro_econ'\).*?create_table\((.*?)\n        \)",
            src,
            re.DOTALL,
        )
        assert macro_block is not None
        block = macro_block.group(0)
        assert "loan_rate_1y" in block
        assert "reserve_ratio" in block


class TestAlembicHeadsSingle:
    """单 head 校验(静态 — 不调 alembic CLI,扫 versions/ 目录).

    AGENTS.md 2026-06-16 P0 双 head 事故回归防护:
    每个 migration 的 revision 应只被一个 down_revision 指向(无 fork).
    """

    def test_no_revision_duplicated_across_files(self):
        """每个 revision id 在所有 migration 文件中唯一."""
        all_migrations = sorted(ALEMBIC_VERSIONS.glob("*.py"))
        revisions = []
        for m in all_migrations:
            src = m.read_text(encoding="utf-8")
            match = re.search(r"revision:\s*str\s*=\s*['\"]([^'\"]+)['\"]", src)
            if match:
                revisions.append(match.group(1))
        # 唯一性
        assert len(revisions) == len(set(revisions)), f"duplicate revisions: {revisions}"

    def test_31_is_terminal_head(self):
        """31_bs_minority_equity 是终端 head.

        2026-08-26:24 不再是 head(被 25 指向)。25 = nocodb 回迁 baseline(结构由回拷建立)。
        2026-07-17:22 不再是 head(被 23 指向)。23 不再是 head(被 24 指向)。
        2026-09-28:28 不再是 head(被 29 指向)。29 = obb_equity_historical 视图(P2 provider 底层)。
2026-10-22:29 不再是 head(被 30 指向)。30 = balance_sheet 补总量列(galaxy-web W2)
        """
        all_migrations = sorted(ALEMBIC_VERSIONS.glob("*.py"))
        twenty_four_rev = "31_bs_minority_equity"
        pointing_to_24 = 0
        for m in all_migrations:
            src = m.read_text(encoding="utf-8")
            match = re.search(r"down_revision.*=\s*['\"]([^'\"]+)['\"]", src)
            if match and match.group(1) == twenty_four_rev:
                pointing_to_24 += 1
        assert (
            pointing_to_24 == 0
        ), f"{twenty_four_rev} 被 {pointing_to_24} 个 migration 指向,应 0(终端 head)"

    def test_19_down_revision_is_18(self):
        """19 的 down_revision = 18_drop_unused_phase02_tables(Phase 03 03-02 重编号)."""
        migration_19 = ALEMBIC_VERSIONS / "19_extend_last_sync_date_schema.py"
        src = migration_19.read_text(encoding="utf-8")
        assert "down_revision" in src and "18_drop_unused_phase02_tables" in src

    def test_migration_18_drops_7_tables(self):
        """范围修订:migration 18 drop 7 表(akshare 4 + baostock 3)."""
        migration_18 = ALEMBIC_VERSIONS / "18_drop_unused_phase02_tables.py"
        src = _read(migration_18)
        assert "revision: str = '18_drop_unused_phase02_tables'" in src
        assert "'17_add_amazingdata_fund_flow'" in src
        # upgrade drop 7 表
        for table in [
            "akshare_stock_fund_flow_daily",
            "akshare_north_fund_flow_daily",
            "akshare_market_fund_flow_daily",
            "akshare_industry_pe_daily",
            "baostock_stock_valuation_daily",
            "baostock_macro_econ",
            "baostock_index_valuation_daily",
        ]:
            assert f"'{table}'" in src, f"migration 18 应 drop {table}"
        # sync_state 清理
        assert "DELETE FROM sync_state" in src
