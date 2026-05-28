from sync.v1 import types_pb2 as _types_pb2
from common.v1 import auth_pb2 as _auth_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StartSchedulerRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class StartSchedulerResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: _Optional[bool] = ...) -> None: ...

class StopSchedulerRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class StopSchedulerResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: _Optional[bool] = ...) -> None: ...

class GetSchedulerStatusRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class GetSchedulerStatusResponse(_message.Message):
    __slots__ = ("running", "last_run_ms", "next_run_ms", "recent_tasks")
    RUNNING_FIELD_NUMBER: _ClassVar[int]
    LAST_RUN_MS_FIELD_NUMBER: _ClassVar[int]
    NEXT_RUN_MS_FIELD_NUMBER: _ClassVar[int]
    RECENT_TASKS_FIELD_NUMBER: _ClassVar[int]
    running: bool
    last_run_ms: int
    next_run_ms: int
    recent_tasks: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, running: _Optional[bool] = ..., last_run_ms: _Optional[int] = ..., next_run_ms: _Optional[int] = ..., recent_tasks: _Optional[_Iterable[str]] = ...) -> None: ...

class GetSchedulerConfigRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class GetSchedulerConfigResponse(_message.Message):
    __slots__ = ("config",)
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    config: _types_pb2.SchedulerConfig
    def __init__(self, config: _Optional[_Union[_types_pb2.SchedulerConfig, _Mapping]] = ...) -> None: ...

class UpdateSchedulerConfigRequest(_message.Message):
    __slots__ = ("config", "user_id")
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    config: _types_pb2.SchedulerConfig
    user_id: str
    def __init__(self, config: _Optional[_Union[_types_pb2.SchedulerConfig, _Mapping]] = ..., user_id: _Optional[str] = ...) -> None: ...

class UpdateSchedulerConfigResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: _Optional[bool] = ...) -> None: ...

class TriggerNowRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class TriggerNowResponse(_message.Message):
    __slots__ = ("task_id",)
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    def __init__(self, task_id: _Optional[str] = ...) -> None: ...
