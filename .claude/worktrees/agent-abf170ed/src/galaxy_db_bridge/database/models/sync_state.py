"""Sync state model for tracking synchronization history."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from galaxy_db_bridge.database.models import Base


class SyncState(Base):
    """Sync state tracking table.

    Tracks sync history to prevent duplicate syncs and allow retry tracking.
    """

    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True)
    sync_type = Column(String(50), nullable=False)  # 'kline_day', 'kline_week', 'calendar'
    period_identifier = Column(String(20), nullable=False)  # '2025-03-28', '2025-W12', '2026'
    sync_status = Column(String(20), nullable=False)  # 'pending', 'running', 'success', 'failed'
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    records_synced = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_sync_state_unique', 'sync_type', 'period_identifier', unique=True),
    )

    def __repr__(self) -> str:
        return f"<SyncState({self.sync_type}, {self.period_identifier}, {self.sync_status})>"