from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class SyncJob(_message.Message):
    __slots__ = ("job_id", "job_type", "status", "started_at_ms", "completed_at_ms", "rows_inserted", "error_message", "user_id")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    JOB_TYPE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    ROWS_INSERTED_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    job_type: str
    status: str
    started_at_ms: int
    completed_at_ms: int
    rows_inserted: int
    error_message: str
    user_id: str
    def __init__(self, job_id: _Optional[str] = ..., job_type: _Optional[str] = ..., status: _Optional[str] = ..., started_at_ms: _Optional[int] = ..., completed_at_ms: _Optional[int] = ..., rows_inserted: _Optional[int] = ..., error_message: _Optional[str] = ..., user_id: _Optional[str] = ...) -> None: ...

class SyncProgress(_message.Message):
    __slots__ = ("job_id", "job_type", "rows_processed", "current_interval", "current_symbol", "status", "updated_at_ms")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    JOB_TYPE_FIELD_NUMBER: _ClassVar[int]
    ROWS_PROCESSED_FIELD_NUMBER: _ClassVar[int]
    CURRENT_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    CURRENT_SYMBOL_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    job_type: str
    rows_processed: int
    current_interval: str
    current_symbol: str
    status: str
    updated_at_ms: int
    def __init__(self, job_id: _Optional[str] = ..., job_type: _Optional[str] = ..., rows_processed: _Optional[int] = ..., current_interval: _Optional[str] = ..., current_symbol: _Optional[str] = ..., status: _Optional[str] = ..., updated_at_ms: _Optional[int] = ...) -> None: ...

class SchedulerConfig(_message.Message):
    __slots__ = ("kline_trigger_hour", "kline_trigger_minute", "calendar_sync_month", "calendar_sync_day", "enabled_intervals", "security_type", "retry_delays_minutes")
    KLINE_TRIGGER_HOUR_FIELD_NUMBER: _ClassVar[int]
    KLINE_TRIGGER_MINUTE_FIELD_NUMBER: _ClassVar[int]
    CALENDAR_SYNC_MONTH_FIELD_NUMBER: _ClassVar[int]
    CALENDAR_SYNC_DAY_FIELD_NUMBER: _ClassVar[int]
    ENABLED_INTERVALS_FIELD_NUMBER: _ClassVar[int]
    SECURITY_TYPE_FIELD_NUMBER: _ClassVar[int]
    RETRY_DELAYS_MINUTES_FIELD_NUMBER: _ClassVar[int]
    kline_trigger_hour: int
    kline_trigger_minute: int
    calendar_sync_month: int
    calendar_sync_day: int
    enabled_intervals: _containers.RepeatedScalarFieldContainer[str]
    security_type: str
    retry_delays_minutes: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, kline_trigger_hour: _Optional[int] = ..., kline_trigger_minute: _Optional[int] = ..., calendar_sync_month: _Optional[int] = ..., calendar_sync_day: _Optional[int] = ..., enabled_intervals: _Optional[_Iterable[str]] = ..., security_type: _Optional[str] = ..., retry_delays_minutes: _Optional[_Iterable[int]] = ...) -> None: ...
