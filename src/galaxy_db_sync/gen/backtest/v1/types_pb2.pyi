from common.v1 import pagination_pb2 as _pagination_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class BacktestRun(_message.Message):
    __slots__ = ("run_id", "strategy_name", "symbol", "start_date_ms", "end_date_ms", "created_at_ms", "is_portfolio", "is_walkforward", "risk_free_rate", "initial_capital", "data_source", "user_id")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    STRATEGY_NAME_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    START_DATE_MS_FIELD_NUMBER: _ClassVar[int]
    END_DATE_MS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    IS_PORTFOLIO_FIELD_NUMBER: _ClassVar[int]
    IS_WALKFORWARD_FIELD_NUMBER: _ClassVar[int]
    RISK_FREE_RATE_FIELD_NUMBER: _ClassVar[int]
    INITIAL_CAPITAL_FIELD_NUMBER: _ClassVar[int]
    DATA_SOURCE_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    strategy_name: str
    symbol: str
    start_date_ms: int
    end_date_ms: int
    created_at_ms: int
    is_portfolio: bool
    is_walkforward: bool
    risk_free_rate: float
    initial_capital: str
    data_source: str
    user_id: str
    def __init__(self, run_id: _Optional[str] = ..., strategy_name: _Optional[str] = ..., symbol: _Optional[str] = ..., start_date_ms: _Optional[int] = ..., end_date_ms: _Optional[int] = ..., created_at_ms: _Optional[int] = ..., is_portfolio: _Optional[bool] = ..., is_walkforward: _Optional[bool] = ..., risk_free_rate: _Optional[float] = ..., initial_capital: _Optional[str] = ..., data_source: _Optional[str] = ..., user_id: _Optional[str] = ...) -> None: ...

class BacktestMetrics(_message.Message):
    __slots__ = ("run_id", "total_return", "cagr_ratio", "max_drawdown", "max_drawdown_duration", "sharpe_ratio", "calmar_ratio", "total_trades", "winning_trades", "win_rate", "profit_loss_ratio", "portfolio_return", "portfolio_cagr", "portfolio_max_drawdown", "portfolio_max_drawdown_duration", "portfolio_sharpe_ratio", "portfolio_calmar_ratio", "turnover", "diversification_ratio", "number_of_assets", "avg_active_positions", "window_count", "avg_wfe", "min_wfe", "max_wfe", "total_oos_return", "avg_oos_sharpe", "avg_oos_max_drawdown")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    TOTAL_RETURN_FIELD_NUMBER: _ClassVar[int]
    CAGR_RATIO_FIELD_NUMBER: _ClassVar[int]
    MAX_DRAWDOWN_FIELD_NUMBER: _ClassVar[int]
    MAX_DRAWDOWN_DURATION_FIELD_NUMBER: _ClassVar[int]
    SHARPE_RATIO_FIELD_NUMBER: _ClassVar[int]
    CALMAR_RATIO_FIELD_NUMBER: _ClassVar[int]
    TOTAL_TRADES_FIELD_NUMBER: _ClassVar[int]
    WINNING_TRADES_FIELD_NUMBER: _ClassVar[int]
    WIN_RATE_FIELD_NUMBER: _ClassVar[int]
    PROFIT_LOSS_RATIO_FIELD_NUMBER: _ClassVar[int]
    PORTFOLIO_RETURN_FIELD_NUMBER: _ClassVar[int]
    PORTFOLIO_CAGR_FIELD_NUMBER: _ClassVar[int]
    PORTFOLIO_MAX_DRAWDOWN_FIELD_NUMBER: _ClassVar[int]
    PORTFOLIO_MAX_DRAWDOWN_DURATION_FIELD_NUMBER: _ClassVar[int]
    PORTFOLIO_SHARPE_RATIO_FIELD_NUMBER: _ClassVar[int]
    PORTFOLIO_CALMAR_RATIO_FIELD_NUMBER: _ClassVar[int]
    TURNOVER_FIELD_NUMBER: _ClassVar[int]
    DIVERSIFICATION_RATIO_FIELD_NUMBER: _ClassVar[int]
    NUMBER_OF_ASSETS_FIELD_NUMBER: _ClassVar[int]
    AVG_ACTIVE_POSITIONS_FIELD_NUMBER: _ClassVar[int]
    WINDOW_COUNT_FIELD_NUMBER: _ClassVar[int]
    AVG_WFE_FIELD_NUMBER: _ClassVar[int]
    MIN_WFE_FIELD_NUMBER: _ClassVar[int]
    MAX_WFE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_OOS_RETURN_FIELD_NUMBER: _ClassVar[int]
    AVG_OOS_SHARPE_FIELD_NUMBER: _ClassVar[int]
    AVG_OOS_MAX_DRAWDOWN_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    total_return: float
    cagr_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    sharpe_ratio: float
    calmar_ratio: float
    total_trades: int
    winning_trades: int
    win_rate: float
    profit_loss_ratio: float
    portfolio_return: float
    portfolio_cagr: float
    portfolio_max_drawdown: float
    portfolio_max_drawdown_duration: int
    portfolio_sharpe_ratio: float
    portfolio_calmar_ratio: float
    turnover: float
    diversification_ratio: float
    number_of_assets: int
    avg_active_positions: float
    window_count: int
    avg_wfe: float
    min_wfe: float
    max_wfe: float
    total_oos_return: float
    avg_oos_sharpe: float
    avg_oos_max_drawdown: float
    def __init__(self, run_id: _Optional[str] = ..., total_return: _Optional[float] = ..., cagr_ratio: _Optional[float] = ..., max_drawdown: _Optional[float] = ..., max_drawdown_duration: _Optional[int] = ..., sharpe_ratio: _Optional[float] = ..., calmar_ratio: _Optional[float] = ..., total_trades: _Optional[int] = ..., winning_trades: _Optional[int] = ..., win_rate: _Optional[float] = ..., profit_loss_ratio: _Optional[float] = ..., portfolio_return: _Optional[float] = ..., portfolio_cagr: _Optional[float] = ..., portfolio_max_drawdown: _Optional[float] = ..., portfolio_max_drawdown_duration: _Optional[int] = ..., portfolio_sharpe_ratio: _Optional[float] = ..., portfolio_calmar_ratio: _Optional[float] = ..., turnover: _Optional[float] = ..., diversification_ratio: _Optional[float] = ..., number_of_assets: _Optional[int] = ..., avg_active_positions: _Optional[float] = ..., window_count: _Optional[int] = ..., avg_wfe: _Optional[float] = ..., min_wfe: _Optional[float] = ..., max_wfe: _Optional[float] = ..., total_oos_return: _Optional[float] = ..., avg_oos_sharpe: _Optional[float] = ..., avg_oos_max_drawdown: _Optional[float] = ...) -> None: ...

class BacktestTrade(_message.Message):
    __slots__ = ("id", "run_id", "symbol", "entry_date_ms", "exit_date_ms", "entry_price", "exit_price", "shares", "pnl", "commission")
    ID_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    ENTRY_DATE_MS_FIELD_NUMBER: _ClassVar[int]
    EXIT_DATE_MS_FIELD_NUMBER: _ClassVar[int]
    ENTRY_PRICE_FIELD_NUMBER: _ClassVar[int]
    EXIT_PRICE_FIELD_NUMBER: _ClassVar[int]
    SHARES_FIELD_NUMBER: _ClassVar[int]
    PNL_FIELD_NUMBER: _ClassVar[int]
    COMMISSION_FIELD_NUMBER: _ClassVar[int]
    id: int
    run_id: str
    symbol: str
    entry_date_ms: int
    exit_date_ms: int
    entry_price: str
    exit_price: str
    shares: str
    pnl: str
    commission: str
    def __init__(self, id: _Optional[int] = ..., run_id: _Optional[str] = ..., symbol: _Optional[str] = ..., entry_date_ms: _Optional[int] = ..., exit_date_ms: _Optional[int] = ..., entry_price: _Optional[str] = ..., exit_price: _Optional[str] = ..., shares: _Optional[str] = ..., pnl: _Optional[str] = ..., commission: _Optional[str] = ...) -> None: ...

class BacktestEquity(_message.Message):
    __slots__ = ("id", "run_id", "trade_date_ms", "equity", "position", "cash", "asset_symbol")
    ID_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    TRADE_DATE_MS_FIELD_NUMBER: _ClassVar[int]
    EQUITY_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    CASH_FIELD_NUMBER: _ClassVar[int]
    ASSET_SYMBOL_FIELD_NUMBER: _ClassVar[int]
    id: int
    run_id: str
    trade_date_ms: int
    equity: str
    position: str
    cash: str
    asset_symbol: str
    def __init__(self, id: _Optional[int] = ..., run_id: _Optional[str] = ..., trade_date_ms: _Optional[int] = ..., equity: _Optional[str] = ..., position: _Optional[str] = ..., cash: _Optional[str] = ..., asset_symbol: _Optional[str] = ...) -> None: ...

class BacktestParam(_message.Message):
    __slots__ = ("id", "run_id", "param_name", "param_value")
    ID_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    PARAM_NAME_FIELD_NUMBER: _ClassVar[int]
    PARAM_VALUE_FIELD_NUMBER: _ClassVar[int]
    id: int
    run_id: str
    param_name: str
    param_value: int
    def __init__(self, id: _Optional[int] = ..., run_id: _Optional[str] = ..., param_name: _Optional[str] = ..., param_value: _Optional[int] = ...) -> None: ...

class BacktestWindow(_message.Message):
    __slots__ = ("id", "run_id", "window_idx", "is_start_date_ms", "is_end_date_ms", "oos_start_date_ms", "oos_end_date_ms", "best_params_json", "is_sharpe", "oos_sharpe", "wfe")
    ID_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    WINDOW_IDX_FIELD_NUMBER: _ClassVar[int]
    IS_START_DATE_MS_FIELD_NUMBER: _ClassVar[int]
    IS_END_DATE_MS_FIELD_NUMBER: _ClassVar[int]
    OOS_START_DATE_MS_FIELD_NUMBER: _ClassVar[int]
    OOS_END_DATE_MS_FIELD_NUMBER: _ClassVar[int]
    BEST_PARAMS_JSON_FIELD_NUMBER: _ClassVar[int]
    IS_SHARPE_FIELD_NUMBER: _ClassVar[int]
    OOS_SHARPE_FIELD_NUMBER: _ClassVar[int]
    WFE_FIELD_NUMBER: _ClassVar[int]
    id: int
    run_id: str
    window_idx: int
    is_start_date_ms: int
    is_end_date_ms: int
    oos_start_date_ms: int
    oos_end_date_ms: int
    best_params_json: str
    is_sharpe: float
    oos_sharpe: float
    wfe: float
    def __init__(self, id: _Optional[int] = ..., run_id: _Optional[str] = ..., window_idx: _Optional[int] = ..., is_start_date_ms: _Optional[int] = ..., is_end_date_ms: _Optional[int] = ..., oos_start_date_ms: _Optional[int] = ..., oos_end_date_ms: _Optional[int] = ..., best_params_json: _Optional[str] = ..., is_sharpe: _Optional[float] = ..., oos_sharpe: _Optional[float] = ..., wfe: _Optional[float] = ...) -> None: ...

class BacktestStability(_message.Message):
    __slots__ = ("id", "run_id", "param_name", "mean", "std", "cv", "level")
    ID_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    PARAM_NAME_FIELD_NUMBER: _ClassVar[int]
    MEAN_FIELD_NUMBER: _ClassVar[int]
    STD_FIELD_NUMBER: _ClassVar[int]
    CV_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    id: int
    run_id: str
    param_name: str
    mean: float
    std: float
    cv: float
    level: str
    def __init__(self, id: _Optional[int] = ..., run_id: _Optional[str] = ..., param_name: _Optional[str] = ..., mean: _Optional[float] = ..., std: _Optional[float] = ..., cv: _Optional[float] = ..., level: _Optional[str] = ...) -> None: ...
