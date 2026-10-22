"""CSTMidnightFileHandler — 按北京午夜显式轮转的日志文件处理器.

替代 ``TimedRotatingFileHandler(when="midnight", atTime=..., utc=False)``:
后者在 CPython 3.14 + TZ=UTC 环境实证静默停写 48h(2026-09-05 00:00 ~
09-08 00:00 北京,期间归档缺失、无任何 Logging error,详见 .work/HISTORY.md
2026-09-09)。轮转逻辑改为显式比对:每次 emit 前检查北京日期,跨日则
归档旧内容(suffix=北京日期)并重开。归档命名与 TRFH 保持一致
(``<base>.YYYYMMDD``),审计 SOP 不受影响。
"""

from __future__ import annotations

import contextlib
import logging
import os

from galaxy_core.shared_kernel.utils.constants import now_cst


class CSTMidnightFileHandler(logging.FileHandler):
    """按北京日界线(00:00 CST)轮转的文件日志处理器.

    与 TRFH 的差异:不依赖 ``rolloverAt`` 时间算术(atTime/utc/DST 陷阱),
    每次写入前直接比对 ``now_cst().date()``,跨日才做归档 + 重开。进程
    长时间冻结后恢复时同样能正确归档(归档名 = 冻结前最后写入日期)。
    """

    def __init__(
        self,
        filename: str,
        backup_count: int = 14,
        encoding: str | None = "utf-8",
        delay: bool = True,
    ) -> None:
        super().__init__(filename, encoding=encoding, delay=delay)
        self._backup_count = backup_count
        self._cst_date = now_cst().date()

    def emit(self, record: logging.LogRecord) -> None:
        """跨北京日则先归档,再走常规写入.

        Handler.handle() 已持有锁,归档的文件操作线程安全;归档自身异常
        走 handleError(stderr),不吞也不阻断本次写入尝试。
        """
        try:
            self._rollover_if_new_cst_day()
        except Exception:
            self.handleError(record)
        super().emit(record)

    def _rollover_if_new_cst_day(self) -> None:
        """北京日期变化时:关流 → 归档旧内容 → 清理超量归档 → 待重开."""
        today = now_cst().date()
        if today <= self._cst_date:
            return

        if self.stream:
            self.stream.close()
            self.stream = None
        archive = f"{self.baseFilename}.{self._cst_date:%Y%m%d}"
        if os.path.exists(archive):
            os.remove(archive)
        if os.path.exists(self.baseFilename):
            os.rename(self.baseFilename, archive)
        self._prune_old_archives()
        self._cst_date = today
        # stream=None:FileHandler.emit 检测到 None 会经 _open() 重新打开

    def _prune_old_archives(self) -> None:
        """超过 backup_count 的最旧归档删除(backup_count<=0 不清理)."""
        if self._backup_count <= 0:
            return
        base = os.path.basename(self.baseFilename)
        directory = os.path.dirname(self.baseFilename) or "."
        try:
            archives = sorted(
                name
                for name in os.listdir(directory)
                if name.startswith(base + ".")
            )
        except OSError:
            return
        for name in archives[: len(archives) - self._backup_count]:
            with contextlib.suppress(OSError):
                os.remove(os.path.join(directory, name))
