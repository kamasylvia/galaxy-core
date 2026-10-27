"""Phase 03 migration 19 + 增量改造静态回归测试(无 DB).

验证 03-02/03-04/03-05 改动:
- migration 19 存在 + down_revision=18 + 加 2 列 + 三模式 CHECK + UNIQUE
- ORM model 三模式兼容
- index/fundflow job 含 IncrementalSyncMixin + _resolve_incremental_range 调用
- 源码无 _resolve_range 残留(固定 7 天反模式已删)
"""

import re
from pathlib import Path

import pytest

ALEMBIC_VERSIONS = Path("alembic/versions")
SRC = Path("data/src/galaxy_core")

MIGRATION_19 = "19_extend_last_sync_date_schema.py"


class TestMigration19Static:
    """migration 19 静态校验."""

    def test_migration_19_exists(self):
        assert (ALEMBIC_VERSIONS / MIGRATION_19).is_file()

    def test_migration_19_down_revision_is_18(self):
        src = (ALEMBIC_VERSIONS / MIGRATION_19).read_text()
        assert "18_drop_unused_phase02_tables" in src
        assert "down_revision" in src

    def test_migration_19_adds_sync_type_scope_key(self):
        src = (ALEMBIC_VERSIONS / MIGRATION_19).read_text()
        assert "sync_type" in src
        assert "scope_key" in src

    def test_migration_19_three_mode_check(self):
        """CHECK 文本含三模式分支."""
        src = (ALEMBIC_VERSIONS / MIGRATION_19).read_text()
        # 三模式都应在 CHECK 定义里
        assert "sync_type IS NOT NULL" in src
        assert "data_type IS NOT NULL" in src
        assert "interval IS NOT NULL" in src

    def test_migration_19_unique_constraint(self):
        src = (ALEMBIC_VERSIONS / MIGRATION_19).read_text()
        assert "uq_last_sync_date_sync_type_scope_key" in src


class TestModelThreeMode:
    """ORM model 三模式兼容."""

    def test_last_sync_date_model_three_mode_check(self):
        """(2026-08-26 nocodb 回迁)旧 CHECK 随整库重建消亡,三模式由 nullable 列承载."""
        from galaxy_core.database.models.last_sync_date import LastSyncDate

        checks = [
            c for c in LastSyncDate.__table__.constraints
            if c.__class__.__name__ == "CheckConstraint"
        ]
        assert checks == []
        cols = {c.name: c for c in LastSyncDate.__table__.columns}
        for name in ("sync_type", "data_type", "interval"):
            assert cols[name].nullable is True

    def test_last_sync_date_model_symbol_nullable(self):
        """三模式兼容:symbol nullable(Phase 1&2 模式无 symbol)."""
        from galaxy_core.database.models.last_sync_date import LastSyncDate

        assert LastSyncDate.__table__.columns["symbol"].nullable is True


class TestJobsUseIncrementalMixin:
    """3 job(exchange/industry/fundflow)继承 IncrementalSyncMixin."""

    def test_exchange_job_inherits_mixin(self):
        from galaxy_core.application.scheduler.jobs.exchange_index_sync_job import (
            ExchangeIndexSyncJob,
        )
        from galaxy_core.application.scheduler.jobs._incremental_mixin import (
            IncrementalSyncMixin,
        )

        assert issubclass(ExchangeIndexSyncJob, IncrementalSyncMixin)

    def test_industry_job_inherits_mixin(self):
        from galaxy_core.application.scheduler.jobs.industry_index_sync_job import (
            IndustryIndexSyncJob,
        )
        from galaxy_core.application.scheduler.jobs._incremental_mixin import (
            IncrementalSyncMixin,
        )

        assert issubclass(IndustryIndexSyncJob, IncrementalSyncMixin)

    def test_fundflow_job_inherits_mixin(self):
        from galaxy_core.application.scheduler.jobs.fundflow_sync_job import (
            FundFlowSyncJob,
        )
        from galaxy_core.application.scheduler.jobs._incremental_mixin import (
            IncrementalSyncMixin,
        )

        assert issubclass(FundFlowSyncJob, IncrementalSyncMixin)


class TestFixed7DayWindowRemoved:
    """固定 7 天 _resolve_range 反模式已从所有 job 删除."""

    @pytest.mark.parametrize(
        "job_file",
        [
            "application/scheduler/jobs/exchange_index_sync_job.py",
            "application/scheduler/jobs/industry_index_sync_job.py",
            "application/scheduler/jobs/fundflow_sync_job.py",
        ],
    )
    def test_no_resolve_range_method(self, job_file):
        """无 _resolve_range 方法定义(被 _resolve_incremental_range 替换)."""
        src = (SRC / job_file).read_text()
        # _resolve_range 方法定义(不含 _resolve_incremental_range)
        # 匹配 'def _resolve_range(' 但不含 'incremental'
        pattern = r"def _resolve_range\([^)]*\)"
        matches = re.findall(pattern, src)
        assert not matches, f"{job_file} 仍有 _resolve_range 方法(应改为 _resolve_incremental_range)"

    def test_no_timedelta_days_7_hardcode_in_fundflow(self):
        """fundflow 无 timedelta(days=7) 硬编码."""
        src = (
            SRC / "application/scheduler/jobs/fundflow_sync_job.py"
        ).read_text()
        assert "timedelta(days=7)" not in src, "fundflow 不应再有固定 7 天窗口"
        assert "_DEFAULT_LOOKBACK_DAYS" not in src

    def test_jobs_call_resolve_incremental_range(self):
        """3 job 都调 _resolve_incremental_range."""
        for job_file in [
            "application/scheduler/jobs/exchange_index_sync_job.py",
            "application/scheduler/jobs/industry_index_sync_job.py",
            "application/scheduler/jobs/fundflow_sync_job.py",
        ]:
            src = (SRC / job_file).read_text()
            assert "_resolve_incremental_range" in src, (
                f"{job_file} 应调 _resolve_incremental_range"
            )


class TestAlembicSingleHead:
    """单 head 校验(防双 head)."""

    def test_31_is_terminal_head(self):
        all_migrations = sorted(ALEMBIC_VERSIONS.glob("*.py"))
        twenty_four_rev = "31_bs_minority_equity"
        pointing_to_24 = 0
        for m in all_migrations:
            src = m.read_text(encoding="utf-8")
            match = re.search(r"down_revision.*=\s*['\"]([^'\"]+)['\"]", src)
            if match and match.group(1) == twenty_four_rev:
                pointing_to_24 += 1
        assert pointing_to_24 == 0, f"{twenty_four_rev} 应是终端 head(0 指向)"

    def test_no_duplicate_revisions(self):
        revisions = {}
        duplicates = []
        for py_file in sorted(ALEMBIC_VERSIONS.glob("*.py")):
            content = py_file.read_text()
            match = re.search(r"^revision\s*[=:]\s*['\"]([0-9a-f]+)['\"]", content, re.M)
            if not match:
                continue
            rev = match.group(1)
            if rev in revisions:
                duplicates.append(f"{rev} in {py_file.name} + {revisions[rev]}")
            revisions[rev] = py_file.name
        assert not duplicates, f"重复 revision(双 head 风险):{duplicates}"
