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


def get_pretrade_ticks(
    trade: pd.Series, ticks: pd.DataFrame, lookback: int = 100
) -> pd.DataFrame:
    """Get N ticks before trade, handling timing edge cases"""
    trade_time = trade["End Time"]
    next_second = trade_time + pd.Timedelta(seconds=1)
    price_col = "bid" if trade["Type"] == "buy" else "ask"
    GAP_THRESH = 0.2  # seconds

    prev_tick = ticks[:trade_time].iloc[-1]
    tick_slice = ticks[trade_time:next_second]

    def is_far(t1, t2):
        return (t2 - t1).total_seconds() > GAP_THRESH

    def price_diff(df):
        return (df[price_col] - trade["End Price"]).abs()

    if tick_slice.empty:
        tick = prev_tick
    else:
        slice = pd.concat([prev_tick.to_frame().T, tick_slice])
        closest_idx = price_diff(slice).idxmin()

        if (
            closest_idx == prev_tick.name
            and is_far(trade_time, tick_slice.index[0])
            and not is_far(prev_tick.name, trade_time)
        ):
            tick = prev_tick
        else:
            closest_idx = price_diff(tick_slice).idxmin()
            closest = tick_slice.loc[closest_idx]

            if closest_idx == tick_slice.index[-1]:
                ref_time = next_second
            else:
                ref_time = tick_slice[closest_idx:].iloc[1].name

            if is_far(closest_idx, ref_time):
                tick = closest
            else:
                tick = ticks[:closest_idx].iloc[-1]

    history = ticks[: tick.name].tail(lookback - 1)
    return pd.concat([history, tick.to_frame().T])


def analyze_time_distribution(trades: pd.DataFrame):
    """分析交易時間分佈"""
    for dim, func in {
        "星期": lambda x: x.dt.day_name(),
        "小時": lambda x: x.dt.hour,
        "分鐘": lambda x: x.dt.minute,
        "秒": lambda x: x.dt.second,
    }.items():
        counts = func(trades["End Time"]).value_counts()
        total = len(trades)

        print(f"\n{dim}維度 Top 5 (佔比)：")
        for value, count in counts.head().items():
            print(f"{value}: {count}次 ({count/total*100:.1f}%)")
    return


def plot_tick_data(fig: go.Figure, ticks: pd.DataFrame):
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
            )
        )
    return


def plot_entry_exit(
    fig: go.Figure,
    trades: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    is_exit: bool = False,
):
    """繪製交易的進入/退出點"""
    col = "End Time" if is_exit else "Time"
    price_col = "End Price" if is_exit else "Price"
    color = "blue" if is_exit else "gray"

    t = trades[(trades[col] >= start) & (trades[col] < end)]
    if not t.empty:
        for _, row in t.iterrows():
            x = row[col]
            fig.add_trace(
                go.Scatter(
                    x=[x, x + pd.Timedelta(seconds=1)],
                    y=[row[price_col], row[price_col]],
                    mode="lines",
                    name=price_col,
                    line=dict(color=color, dash="dash"),
                )
            )
    return


def create_interactive_view(trades: pd.DataFrame, ticks: pd.DataFrame, idx: int = 0):
    """Create interactive Plotly widget for browsing trades"""
    i_input = widgets.IntText(description="i:", value=idx)
    button_prev = widgets.Button(description="<")
    button_next = widgets.Button(description=">")
    view_mode = widgets.ToggleButtons(
        options=["Time", "Tick"],  # Time: by seconds, Tick: by tick index
        value="Tick",
    )

    fig = make_subplots(rows=1, cols=1)
    fig_widget = go.FigureWidget(fig)
    fig_widget.update_layout(height=600)

    def update_plot(idx: int):
        i_input.value = idx
        with fig_widget.batch_update():
            fig_widget.data = []
            trade = trades.iloc[idx]

            if view_mode.value == "Time":
                x = trade["End Time"]
                start = x - pd.Timedelta(seconds=10)
                end = x + pd.Timedelta(seconds=1)
                tick_slice = ticks[start:end]

                plot_tick_data(fig_widget, tick_slice)
                plot_entry_exit(fig_widget, trades, start, end, is_exit=False)
                plot_entry_exit(fig_widget, trades, start, end, is_exit=True)

                x_title = "Time"
                x_type = "date"
            else:
                tick_slice = get_pretrade_ticks(trade, ticks, lookback=100).reset_index(
                    drop=True
                )
                plot_tick_data(fig_widget, tick_slice)

                x_title = "Tick Index"
                x_type = "linear"

            fig_widget.update_layout(
                title=f"USDJPY Trade Analysis: {idx}",
                hovermode="x unified",
                hoverdistance=100,
                xaxis_title=x_title,
                xaxis_type=x_type,
                yaxis_title="Price",
            )

    last_update = {"time": 0}
    throttle_delay = 0.2  # Prevent rapid clicking lag

    def throttled_update(x: int):
        current = time.time()
        if current - last_update["time"] > throttle_delay:
            new_idx = max(0, min(len(trades) - 1, i_input.value + x))
            update_plot(new_idx)
            last_update["time"] = current

    button_prev.on_click(lambda _: throttled_update(-1))
    button_next.on_click(lambda _: throttled_update(1))
    view_mode.observe(lambda _: update_plot(i_input.value), names="value")

    controls = widgets.HBox(
        [view_mode, button_prev, i_input, button_next],
        layout=widgets.Layout(justify_content="center"),
    )

    display(controls)
    display(fig_widget)
    update_plot(idx)
    return


trades, ticks = load_data()
create_interactive_view(trades, ticks, idx=0)
