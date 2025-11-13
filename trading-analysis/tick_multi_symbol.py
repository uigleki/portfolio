import time
from pathlib import Path

import ipywidgets as widgets
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DATA_DIR = Path("../data")


def load_data(
    symbol: str = "usdjpy", trade_type: str = "buy"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """載入交易資料和tick資料"""
    trades = pd.read_csv(DATA_DIR / "20240923.csv").dropna()
    trades["Type"] = trades["Type"].str.strip()
    trades = (
        trades[(trades["Symbol"] == symbol) & (trades["Type"] == trade_type)]
        .iloc[1:]
        .drop(columns="frame_pos")
        .reset_index(drop=True)
    )
    trades[["Time", "End Time"]] = trades[["Time", "End Time"]].apply(pd.to_datetime)
    ticks = pd.read_parquet(DATA_DIR / f"{symbol.upper()}_20240923.parquet")
    return trades, ticks


def plot_tick_data(fig: go.Figure, ticks: pd.DataFrame, row: int, col: int):
    """繪製tick資料"""
    for price_type, color, opacity in [
        ("ask", "green", 0.2),
        ("bid", "red", 1.0),
    ]:
        fig.add_trace(
            go.Scatter(
                x=ticks.index,
                y=ticks[price_type],
                mode="lines",
                name=price_type.capitalize(),
                line=dict(color=color, shape="hv"),
                opacity=opacity,
            ),
            row=row,
            col=col,
        )
    return


def plot_entry_exit(
    fig: go.Figure,
    trades: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    row: int,
    col: int,
    is_exit: bool = False,
):
    """繪製交易的進入/退出點"""
    col_name = "End Time" if is_exit else "Time"
    price_col = "End Price" if is_exit else "Price"
    color = "blue" if is_exit else "gray"

    t = trades[(trades[col_name] >= start) & (trades[col_name] < end)]
    if not t.empty:
        for _, row_data in t.iterrows():
            x = row_data[col_name]
            fig.add_trace(
                go.Scatter(
                    x=[x, x + pd.Timedelta(seconds=1)],
                    y=[row_data[price_col], row_data[price_col]],
                    mode="lines",
                    name=price_col,
                    line=dict(color=color, dash="dash"),
                ),
                row=row,
                col=col,
            )
    return


def create_interactive_view(
    trades_dict: dict[str, pd.DataFrame],
    ticks_dict: dict[str, pd.DataFrame],
    idx: int = 0,
):
    """Create multi-symbol synchronized view for trade correlation analysis"""
    i_input = widgets.IntText(description="i:", value=idx)
    button_prev = widgets.Button(description="<")
    button_next = widgets.Button(description=">")
    window_slider = widgets.IntSlider(
        value=10,
        min=1,
        max=60,
        step=1,
        description="Window (s):",
        continuous_update=False,
    )

    fig = make_subplots(
        rows=len(trades_dict), cols=1, shared_xaxes=True, vertical_spacing=0.02
    )
    fig_widget = go.FigureWidget(fig)
    fig_widget.update_layout(height=300 * len(trades_dict))

    def update_plot(idx: int):
        i_input.value = idx
        with fig_widget.batch_update():
            fig_widget.data = []

            # Use first symbol's trade time as reference for all symbols
            primary_trades = list(trades_dict.values())[0]
            trade = primary_trades.iloc[idx]
            x = trade["End Time"]
            start = x - pd.Timedelta(seconds=window_slider.value)
            end = x + pd.Timedelta(seconds=1)

            for i, (symbol, trades) in enumerate(trades_dict.items(), start=1):
                tick_slice = ticks_dict[symbol][start:end]

                plot_tick_data(fig_widget, tick_slice, row=i, col=1)
                plot_entry_exit(
                    fig_widget, trades, start, end, row=i, col=1, is_exit=False
                )
                plot_entry_exit(
                    fig_widget, trades, start, end, row=i, col=1, is_exit=True
                )

                fig_widget.update_yaxes(
                    title_text=f"{symbol.upper()} Price", row=i, col=1
                )

            fig_widget.update_layout(
                title=f"Trade Analysis: {idx}",
                hovermode="x unified",
                hoverdistance=100,
            )

    last_update = {"time": 0}
    throttle_delay = 0.2

    def throttled_update(x: int):
        current = time.time()
        if current - last_update["time"] > throttle_delay:
            new_idx = max(
                0, min(len(list(trades_dict.values())[0]) - 1, i_input.value + x)
            )
            update_plot(new_idx)
            last_update["time"] = current

    button_prev.on_click(lambda _: throttled_update(-1))
    button_next.on_click(lambda _: throttled_update(1))
    window_slider.observe(lambda _: update_plot(i_input.value), names="value")

    controls = widgets.HBox(
        [button_prev, i_input, button_next, window_slider],
        layout=widgets.Layout(justify_content="center"),
    )

    display(controls)
    display(fig_widget)
    update_plot(idx)
    return


symbols = [
    "usdjpy",
    "eurjpy",
    "xauusd",
]

trades_dict = {}
ticks_dict = {}
for symbol in symbols:
    trades, ticks = load_data(symbol=symbol)
    trades_dict[symbol] = trades
    ticks_dict[symbol] = ticks

create_interactive_view(trades_dict, ticks_dict, idx=0)
