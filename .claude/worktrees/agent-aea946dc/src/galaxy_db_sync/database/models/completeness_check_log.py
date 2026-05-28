"""Completeness check log model for tracking daily integrity checks.

Per D-22: Separate from sync_state table for clear semantics and analysis.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Index
from galaxy_db_sync.database.models import Base


class CompletenessCheckLog(Base):
    """Completeness check log table.

    Records daily integrity check results for analysis and debugging.
    """

    __tablename__ = "completeness_check_log"

    id = Column(Integer, primary_key=True)
    check_type = Column(String(30), nullable=False)  # 'daily_17pm', 'post_sync'
    check_date = Column(String(10), nullable=False)  # '2025-03-28' (date of data checked)
    check_intervals = Column(JSON, nullable=False)  # ['day', 'week'] - intervals checked
    symbols_checked = Column(Integer, default=0)  # number of symbols checked
    total_missing = Column(Integer, default=0)  # total missing data points found
    repair_triggered = Column(String(10), default="no")  # 'yes', 'no', 'partial'
    repair_result = Column(Text, nullable=True)  # repair outcome details
    check_duration_ms = Column(Integer, default=0)  # check execution time
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_completeness_check_date', 'check_date'),
        Index('idx_completeness_check_type_date', 'check_type', 'check_date'),
    )

    def __repr__(self) -> str:
        return f"<CompletenessCheckLog({self.check_type}, {self.check_date}, missing={self.total_missing})>"