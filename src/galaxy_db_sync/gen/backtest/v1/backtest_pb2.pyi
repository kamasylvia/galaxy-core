from backtest.v1 import types_pb2 as _types_pb2
from common.v1 import pagination_pb2 as _pagination_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ListRunsRequest(_message.Message):
    __slots__ = ("strategy_name", "symbol", "start_date_ms", "end_date_ms", "page", "user_id")
    STRATEGY_NAME_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    START_DATE_MS_FIELD_NUMBER: _ClassVar[int]
    END_DATE_MS_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    strategy_name: str
    symbol: str
    start_date_ms: int
    end_date_ms: int
    page: _pagination_pb2.PageRequest
    user_id: str
    def __init__(self, strategy_name: _Optional[str] = ..., symbol: _Optional[str] = ..., start_date_ms: _Optional[int] = ..., end_date_ms: _Optional[int] = ..., page: _Optional[_Union[_pagination_pb2.PageRequest, _Mapping]] = ..., user_id: _Optional[str] = ...) -> None: ...

class ListRunsResponse(_message.Message):
    __slots__ = ("runs", "page")
    RUNS_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    runs: _containers.RepeatedCompositeFieldContainer[_types_pb2.BacktestRun]
    page: _pagination_pb2.PageResponse
    def __init__(self, runs: _Optional[_Iterable[_Union[_types_pb2.BacktestRun, _Mapping]]] = ..., page: _Optional[_Union[_pagination_pb2.PageResponse, _Mapping]] = ...) -> None: ...

class GetRunDetailRequest(_message.Message):
    __slots__ = ("run_id", "user_id")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    user_id: str
    def __init__(self, run_id: _Optional[str] = ..., user_id: _Optional[str] = ...) -> None: ...

class GetRunDetailResponse(_message.Message):
    __slots__ = ("run", "metrics", "params", "windows", "equity_archived")
    RUN_FIELD_NUMBER: _ClassVar[int]
    METRICS_FIELD_NUMBER: _ClassVar[int]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    WINDOWS_FIELD_NUMBER: _ClassVar[int]
    EQUITY_ARCHIVED_FIELD_NUMBER: _ClassVar[int]
    run: _types_pb2.BacktestRun
    metrics: _types_pb2.BacktestMetrics
    params: _containers.RepeatedCompositeFieldContainer[_types_pb2.BacktestParam]
    windows: _containers.RepeatedCompositeFieldContainer[_types_pb2.BacktestWindow]
    equity_archived: bool
    def __init__(self, run: _Optional[_Union[_types_pb2.BacktestRun, _Mapping]] = ..., metrics: _Optional[_Union[_types_pb2.BacktestMetrics, _Mapping]] = ..., params: _Optional[_Iterable[_Union[_types_pb2.BacktestParam, _Mapping]]] = ..., windows: _Optional[_Iterable[_Union[_types_pb2.BacktestWindow, _Mapping]]] = ..., equity_archived: _Optional[bool] = ...) -> None: ...

class GetMetricsRequest(_message.Message):
    __slots__ = ("run_id", "user_id")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    user_id: str
    def __init__(self, run_id: _Optional[str] = ..., user_id: _Optional[str] = ...) -> None: ...

class GetMetricsResponse(_message.Message):
    __slots__ = ("metrics",)
    METRICS_FIELD_NUMBER: _ClassVar[int]
    metrics: _types_pb2.BacktestMetrics
    def __init__(self, metrics: _Optional[_Union[_types_pb2.BacktestMetrics, _Mapping]] = ...) -> None: ...

class StartRunRequest(_message.Message):
    __slots__ = ("strategy_config_json", "user_id")
    STRATEGY_CONFIG_JSON_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    strategy_config_json: str
    user_id: str
    def __init__(self, strategy_config_json: _Optional[str] = ..., user_id: _Optional[str] = ...) -> None: ...

class StartRunResponse(_message.Message):
    __slots__ = ("run_id",)
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    def __init__(self, run_id: _Optional[str] = ...) -> None: ...

class GetRunStatusRequest(_message.Message):
    __slots__ = ("run_id", "user_id")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    user_id: str
    def __init__(self, run_id: _Optional[str] = ..., user_id: _Optional[str] = ...) -> None: ...

class GetRunStatusResponse(_message.Message):
    __slots__ = ("status", "error_message", "updated_at_ms")
    class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_UNSPECIFIED: _ClassVar[GetRunStatusResponse.Status]
        STATUS_PENDING: _ClassVar[GetRunStatusResponse.Status]
        STATUS_RUNNING: _ClassVar[GetRunStatusResponse.Status]
        STATUS_COMPLETED: _ClassVar[GetRunStatusResponse.Status]
        STATUS_FAILED: _ClassVar[GetRunStatusResponse.Status]
    STATUS_UNSPECIFIED: GetRunStatusResponse.Status
    STATUS_PENDING: GetRunStatusResponse.Status
    STATUS_RUNNING: GetRunStatusResponse.Status
    STATUS_COMPLETED: GetRunStatusResponse.Status
    STATUS_FAILED: GetRunStatusResponse.Status
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    status: GetRunStatusResponse.Status
    error_message: str
    updated_at_ms: int
    def __init__(self, status: _Optional[_Union[GetRunStatusResponse.Status, str]] = ..., error_message: _Optional[str] = ..., updated_at_ms: _Optional[int] = ...) -> None: ...

class GetEquityRequest(_message.Message):
    __slots__ = ("run_id", "user_id")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    user_id: str
    def __init__(self, run_id: _Optional[str] = ..., user_id: _Optional[str] = ...) -> None: ...

class GetEquityResponse(_message.Message):
    __slots__ = ("points", "is_last")
    POINTS_FIELD_NUMBER: _ClassVar[int]
    IS_LAST_FIELD_NUMBER: _ClassVar[int]
    points: _containers.RepeatedCompositeFieldContainer[_types_pb2.BacktestEquity]
    is_last: bool
    def __init__(self, points: _Optional[_Iterable[_Union[_types_pb2.BacktestEquity, _Mapping]]] = ..., is_last: _Optional[bool] = ...) -> None: ...

class GetTradesRequest(_message.Message):
    __slots__ = ("run_id", "user_id")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    user_id: str
    def __init__(self, run_id: _Optional[str] = ..., user_id: _Optional[str] = ...) -> None: ...

class GetTradesResponse(_message.Message):
    __slots__ = ("trades", "is_last")
    TRADES_FIELD_NUMBER: _ClassVar[int]
    IS_LAST_FIELD_NUMBER: _ClassVar[int]
    trades: _containers.RepeatedCompositeFieldContainer[_types_pb2.BacktestTrade]
    is_last: bool
    def __init__(self, trades: _Optional[_Iterable[_Union[_types_pb2.BacktestTrade, _Mapping]]] = ..., is_last: _Optional[bool] = ...) -> None: ...

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
