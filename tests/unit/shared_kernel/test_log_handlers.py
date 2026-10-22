"""CSTMidnightFileHandler 单元测试(2026-09-09,替换 TimedRotatingFileHandler).

背景:TRFH(when="midnight", atTime, utc=False)在 CPython 3.14 静默停写 48h
(归档缺失、无 Logging error,见 .work/HISTORY.md 2026-09-09)。本处理器按北京日期
显式轮转,用例覆盖:跨日归档、同日不归档、超量归档清理。
"""

import logging
from datetime import datetime

import pytest

from galaxy_core.shared_kernel.utils.constants import CST
from galaxy_core.shared_kernel.utils.log_handlers import CSTMidnightFileHandler

_LOGGER_NAME = "test_cst_midnight_handler"


def _dt(y: int, m: int, d: int, h: int = 12) -> datetime:
    return datetime(y, m, d, h, 0, 0, tzinfo=CST)


@pytest.fixture
def logger():
    """独立 logger(不向 root 传播),用例后清理 handler."""
    log = logging.getLogger(_LOGGER_NAME)
    log.setLevel(logging.INFO)
    log.propagate = False
    for h in list(log.handlers):
        log.removeHandler(h)
    yield log
    for h in list(log.handlers):
        h.close()
        log.removeHandler(h)


def _patch_now(monkeypatch, state):
    monkeypatch.setattr(
        "galaxy_core.shared_kernel.utils.log_handlers.now_cst",
        lambda: state["now"],
    )


class TestCSTMidnightFileHandler:
    def test_same_day_writes_without_archive(self, tmp_path, monkeypatch, logger):
        """同北京日内多次写入:不归档,内容全在 base 文件."""
        state = {"now": _dt(2026, 9, 8, 10)}
        _patch_now(monkeypatch, state)
        log_file = tmp_path / "app.log"
        handler = CSTMidnightFileHandler(str(log_file), backup_count=14)
        logger.addHandler(handler)

        logger.info("first")
        logger.info("second")
        handler.flush()

        assert log_file.read_text(encoding="utf-8").count("first") == 1
        assert "second" in log_file.read_text(encoding="utf-8")
        assert not (tmp_path / "app.log.20260908").exists()

    def test_rollover_on_cst_date_change(self, tmp_path, monkeypatch, logger):
        """跨北京日:旧内容归档为 .YYYYMMDD,新内容写 base 文件."""
        state = {"now": _dt(2026, 9, 8, 23)}
        _patch_now(monkeypatch, state)
        log_file = tmp_path / "app.log"
        handler = CSTMidnightFileHandler(str(log_file), backup_count=14)
        logger.addHandler(handler)

        logger.info("day1-line")
        handler.flush()

        state["now"] = _dt(2026, 9, 9, 8)
        logger.info("day2-line")
        handler.flush()

        archive = tmp_path / "app.log.20260908"
        assert archive.exists()
        assert "day1-line" in archive.read_text(encoding="utf-8")
        base_text = log_file.read_text(encoding="utf-8")
        assert "day2-line" in base_text
        assert "day1-line" not in base_text

    def test_multi_day_freeze_archives_with_last_write_date(
        self, tmp_path, monkeypatch, logger
    ):
        """冻结跨多日后恢复:归档名 = 最后写入日期(内容准确),继续写入."""
        state = {"now": _dt(2026, 9, 5, 22)}
        _patch_now(monkeypatch, state)
        log_file = tmp_path / "app.log"
        handler = CSTMidnightFileHandler(str(log_file), backup_count=14)
        logger.addHandler(handler)
        logger.info("before-freeze")
        handler.flush()

        state["now"] = _dt(2026, 9, 8, 0)  # 冻结 3 天
        logger.info("after-freeze")
        handler.flush()

        archive = tmp_path / "app.log.20260905"
        assert archive.exists()
        assert "before-freeze" in archive.read_text(encoding="utf-8")
        assert "after-freeze" in log_file.read_text(encoding="utf-8")

    def test_prunes_archives_beyond_backup_count(
        self, tmp_path, monkeypatch, logger
    ):
        """归档数超 backup_count:最旧者被清理."""
        state = {"now": _dt(2026, 9, 8, 10)}
        _patch_now(monkeypatch, state)
        log_file = tmp_path / "app.log"
        handler = CSTMidnightFileHandler(str(log_file), backup_count=2)
        logger.addHandler(handler)
        # 预置 3 个旧归档
        for d in ("20260905", "20260906", "20260907"):
            (tmp_path / f"app.log.{d}").write_text("old", encoding="utf-8")

        # 9/8 先写入(当日有内容才会归档出 app.log.20260908)
        logger.info("day8")
        handler.flush()

        state["now"] = _dt(2026, 9, 9, 10)
        logger.info("new-day")
        handler.flush()

        assert not (tmp_path / "app.log.20260905").exists()
        assert not (tmp_path / "app.log.20260906").exists()
        assert (tmp_path / "app.log.20260907").exists()
        # 本次归档的 9/8 也保留
        assert (tmp_path / "app.log.20260908").exists()
