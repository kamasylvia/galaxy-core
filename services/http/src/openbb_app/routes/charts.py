"""Candlestick chart data (pure AmazingData, no router - called by equity_cn)."""

import json

import plotly.graph_objects as go

from openbb_app.core.plotly_config import (
    apply_config_to_figure,
    create_base_layout,
    get_chart_colors,
)


def get_chart_data(
    ticker: str,
    interval: str,
    interval_multiplier: int,
    start_date: str,
    end_date: str,
) -> dict:
    from mysharelib.tools import get_valid_date, normalize_symbol

    from openbb_app.core.financials import get_historical_prices

    _, _, market = normalize_symbol(ticker)
    if market not in ("SH", "SZ", "BJ"):
        raise ValueError(f"pure-amazingdata mode: no HK/overseas candles for {ticker}")
    start_dt = get_valid_date(start_date)
    end_dt = get_valid_date(end_date)
    data = get_historical_prices(ticker, interval, interval_multiplier, str(start_dt), str(end_dt))
    theme: str = "dark"
    colors = get_chart_colors(theme)

    figure = go.Figure(
        layout=create_base_layout(
            x_title="Date", y_title="Price", y_dtype="$,.4f", theme=theme
        )
    )
    figure.add_candlestick(
        x=data.index,
        open=data["open"],
        high=data["high"],
        low=data["low"],
        close=data["close"],
        name="Price",
        increasing_line_color=colors["positive"],
        decreasing_line_color=colors["negative"],
    )
    figure.update_layout(
        yaxis={
            "rangemode": "nonnegative",
            "zeroline": True,
            "zerolinewidth": 2,
            "zerolinecolor": "lightgrey",
        },
    )
    figure = apply_config_to_figure(figure, theme=theme)

    figure_json = figure.to_json()
    return json.loads(figure_json)
