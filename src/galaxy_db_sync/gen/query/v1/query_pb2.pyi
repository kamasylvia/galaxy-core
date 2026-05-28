from common.v1 import pagination_pb2 as _pagination_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Operator(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OPERATOR_UNSPECIFIED: _ClassVar[Operator]
    OPERATOR_EQ: _ClassVar[Operator]
    OPERATOR_NE: _ClassVar[Operator]
    OPERATOR_LT: _ClassVar[Operator]
    OPERATOR_LTE: _ClassVar[Operator]
    OPERATOR_GT: _ClassVar[Operator]
    OPERATOR_GTE: _ClassVar[Operator]
    OPERATOR_IN: _ClassVar[Operator]
    OPERATOR_BETWEEN: _ClassVar[Operator]
    OPERATOR_LIKE: _ClassVar[Operator]
OPERATOR_UNSPECIFIED: Operator
OPERATOR_EQ: Operator
OPERATOR_NE: Operator
OPERATOR_LT: Operator
OPERATOR_LTE: Operator
OPERATOR_GT: Operator
OPERATOR_GTE: Operator
OPERATOR_IN: Operator
OPERATOR_BETWEEN: Operator
OPERATOR_LIKE: Operator

class Filter(_message.Message):
    __slots__ = ("column", "op", "values")
    COLUMN_FIELD_NUMBER: _ClassVar[int]
    OP_FIELD_NUMBER: _ClassVar[int]
    VALUES_FIELD_NUMBER: _ClassVar[int]
    column: str
    op: Operator
    values: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, column: _Optional[str] = ..., op: _Optional[_Union[Operator, str]] = ..., values: _Optional[_Iterable[str]] = ...) -> None: ...

class QueryTableRequest(_message.Message):
    __slots__ = ("table", "columns", "filters", "page", "user_id")
    TABLE_FIELD_NUMBER: _ClassVar[int]
    COLUMNS_FIELD_NUMBER: _ClassVar[int]
    FILTERS_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    table: str
    columns: _containers.RepeatedScalarFieldContainer[str]
    filters: _containers.RepeatedCompositeFieldContainer[Filter]
    page: _pagination_pb2.PageRequest
    user_id: str
    def __init__(self, table: _Optional[str] = ..., columns: _Optional[_Iterable[str]] = ..., filters: _Optional[_Iterable[_Union[Filter, _Mapping]]] = ..., page: _Optional[_Union[_pagination_pb2.PageRequest, _Mapping]] = ..., user_id: _Optional[str] = ...) -> None: ...

class QueryTableResponse(_message.Message):
    __slots__ = ("rows", "page")
    ROWS_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    rows: _containers.RepeatedCompositeFieldContainer[Row]
    page: _pagination_pb2.PageResponse
    def __init__(self, rows: _Optional[_Iterable[_Union[Row, _Mapping]]] = ..., page: _Optional[_Union[_pagination_pb2.PageResponse, _Mapping]] = ...) -> None: ...

class Row(_message.Message):
    __slots__ = ("cells",)
    class CellsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    CELLS_FIELD_NUMBER: _ClassVar[int]
    cells: _containers.ScalarMap[str, str]
    def __init__(self, cells: _Optional[_Mapping[str, str]] = ...) -> None: ...

class StreamTableRowsRequest(_message.Message):
    __slots__ = ("table", "columns", "filters", "user_id")
    TABLE_FIELD_NUMBER: _ClassVar[int]
    COLUMNS_FIELD_NUMBER: _ClassVar[int]
    FILTERS_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    table: str
    columns: _containers.RepeatedScalarFieldContainer[str]
    filters: _containers.RepeatedCompositeFieldContainer[Filter]
    user_id: str
    def __init__(self, table: _Optional[str] = ..., columns: _Optional[_Iterable[str]] = ..., filters: _Optional[_Iterable[_Union[Filter, _Mapping]]] = ..., user_id: _Optional[str] = ...) -> None: ...

class StreamTableRowsResponse(_message.Message):
    __slots__ = ("rows", "is_last")
    ROWS_FIELD_NUMBER: _ClassVar[int]
    IS_LAST_FIELD_NUMBER: _ClassVar[int]
    rows: _containers.RepeatedCompositeFieldContainer[Row]
    is_last: bool
    def __init__(self, rows: _Optional[_Iterable[_Union[Row, _Mapping]]] = ..., is_last: _Optional[bool] = ...) -> None: ...

class GetSchemaRequest(_message.Message):
    __slots__ = ("table", "user_id")
    TABLE_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    table: str
    user_id: str
    def __init__(self, table: _Optional[str] = ..., user_id: _Optional[str] = ...) -> None: ...

class ColumnSchema(_message.Message):
    __slots__ = ("name", "type", "comment", "nullable")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    COMMENT_FIELD_NUMBER: _ClassVar[int]
    NULLABLE_FIELD_NUMBER: _ClassVar[int]
    name: str
    type: str
    comment: str
    nullable: bool
    def __init__(self, name: _Optional[str] = ..., type: _Optional[str] = ..., comment: _Optional[str] = ..., nullable: _Optional[bool] = ...) -> None: ...

class GetSchemaResponse(_message.Message):
    __slots__ = ("columns",)
    COLUMNS_FIELD_NUMBER: _ClassVar[int]
    columns: _containers.RepeatedCompositeFieldContainer[ColumnSchema]
    def __init__(self, columns: _Optional[_Iterable[_Union[ColumnSchema, _Mapping]]] = ...) -> None: ...
