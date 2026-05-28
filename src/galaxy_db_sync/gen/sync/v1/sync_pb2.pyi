from sync.v1 import types_pb2 as _types_pb2
from common.v1 import pagination_pb2 as _pagination_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StartManualSyncRequest(_message.Message):
    __slots__ = ("security_type", "enabled_intervals", "start_date_ms", "end_date_ms", "user_id")
    SECURITY_TYPE_FIELD_NUMBER: _ClassVar[int]
    ENABLED_INTERVALS_FIELD_NUMBER: _ClassVar[int]
    START_DATE_MS_FIELD_NUMBER: _ClassVar[int]
    END_DATE_MS_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    security_type: str
    enabled_intervals: _containers.RepeatedScalarFieldContainer[str]
    start_date_ms: int
    end_date_ms: int
    user_id: str
    def __init__(self, security_type: _Optional[str] = ..., enabled_intervals: _Optional[_Iterable[str]] = ..., start_date_ms: _Optional[int] = ..., end_date_ms: _Optional[int] = ..., user_id: _Optional[str] = ...) -> None: ...

class StartManualSyncResponse(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class StreamSyncProgressRequest(_message.Message):
    __slots__ = ("job_id", "user_id")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    user_id: str
    def __init__(self, job_id: _Optional[str] = ..., user_id: _Optional[str] = ...) -> None: ...

class ListSyncJobsRequest(_message.Message):
    __slots__ = ("job_type", "page", "user_id")
    JOB_TYPE_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    job_type: str
    page: _pagination_pb2.PageRequest
    user_id: str
    def __init__(self, job_type: _Optional[str] = ..., page: _Optional[_Union[_pagination_pb2.PageRequest, _Mapping]] = ..., user_id: _Optional[str] = ...) -> None: ...

class ListSyncJobsResponse(_message.Message):
    __slots__ = ("jobs", "page")
    JOBS_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    jobs: _containers.RepeatedCompositeFieldContainer[_types_pb2.SyncJob]
    page: _pagination_pb2.PageResponse
    def __init__(self, jobs: _Optional[_Iterable[_Union[_types_pb2.SyncJob, _Mapping]]] = ..., page: _Optional[_Union[_pagination_pb2.PageResponse, _Mapping]] = ...) -> None: ...

class EchoRequest(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: _Optional[str] = ...) -> None: ...

class EchoResponse(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: _Optional[str] = ...) -> None: ...
