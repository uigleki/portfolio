import warnings
from pathlib import Path

import numpy as np  # noqa
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from skopt import BayesSearchCV
from skopt.space import Categorical, Integer

warnings.filterwarnings("ignore")

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
    """Get N ticks before trade entry by matching the exact entry price"""
    trade_time = trade["End Time"]
    next_second = trade_time + pd.Timedelta(seconds=1)

    tick_slice = ticks[trade_time:next_second]
    if tick_slice.empty:
        matched_time = ticks[trade_time:].index[0]
    else:
        price_col = "bid" if trade["Type"] == "buy" else "ask"
        matched_time = (tick_slice[price_col] - trade["End Price"]).abs().idxmin()

    return ticks[:matched_time].tail(lookback)


def split_tick_windows(
    symbol: str = "usdjpy", trade_type: str = "buy", lookback: int = 100
) -> tuple[list[pd.DataFrame], list[pd.DataFrame]]:
    """Create positive (entry point) and negative (10 ticks before) samples"""
    trades, ticks = load_data(symbol, trade_type)

    pos, neg = [], []
    for _, trade in trades.iterrows():
        tick_window = get_pretrade_ticks(trade, ticks, lookback + 10)
        pos.append(tick_window[10:])  # Last 100 ticks (entry moment)
        neg.append(tick_window[:-10])  # 10 ticks earlier (non-entry)

    return pos, neg


def train_model(
    X_train: pd.DataFrame, y_train: pd.Series, param_space: dict
) -> BayesSearchCV:
    """訓練模型並執行Bayesian參數搜尋"""
    bayes_search = BayesSearchCV(
        RandomForestClassifier(random_state=42),
        param_space,
        n_iter=50,
        cv=5,
        n_jobs=-1,
        verbose=0,
        random_state=42,
    )
    bayes_search.fit(X_train, y_train)
    return bayes_search


def evaluate_model(
    model: BayesSearchCV, X_test: pd.DataFrame, y_test: pd.Series, X: pd.DataFrame
) -> pd.DataFrame:
    """評估模型效能並返回特徵重要性"""
    y_pred = model.predict(X_test)
    print("\n模型評估報告：")
    print(classification_report(y_test, y_pred))

    feature_importance = pd.DataFrame(
        {"feature": X.columns, "importance": model.best_estimator_.feature_importances_}
    ).sort_values("importance", ascending=False)

    print("\n前30個最重要的特徵：")
    print(feature_importance.head(30))
    print(f"\n總特徵數：{len(feature_importance)}")
    print("\n最佳模型參數：")
    print(model.best_params_)

    return feature_importance


def train_evaluate_model(param_space: dict):
    """執行完整的模型訓練和評估流程"""
    pos, neg = split_tick_windows()
    pos_features = extract_features(pos, 1)
    neg_features = extract_features(neg, 0)

    features = pd.concat([pos_features, neg_features], ignore_index=True)
    X = features.drop("label", axis=1)
    y = features["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = train_model(X_train, y_train, param_space)
    _ = evaluate_model(model, X_test, y_test, X)
    return


def extract_features(df_list: list[pd.DataFrame], label: int) -> pd.DataFrame:
    """從tick資料列表中提取特徵"""
    all_features = []
    for df in df_list:
        features = cal_features(df)
        all_features.append(features)

    features_df = pd.DataFrame(all_features)
    features_df["label"] = label
    return features_df


param_space = {
    "n_estimators": Integer(100, 300),
    "max_depth": Integer(10, 100),
    "min_samples_split": Integer(2, 10),
    "min_samples_leaf": Integer(1, 10),
    "max_features": Categorical(["sqrt", "log2"]),
}


def cal_time(df: pd.DataFrame, prefix: str = "") -> dict:
    """Time interval features: sudden changes in tick frequency"""
    features = {}
    time_diffs = df.index.to_series().diff().dt.total_seconds()

    if len(time_diffs) >= 1:
        last_time_diff = time_diffs.iloc[-1]
        mean_time = time_diffs.mean() or 1
        std_time = time_diffs.std() or 1

        features.update(
            {
                f"{prefix}time_diff": last_time_diff,
                f"{prefix}time_ratio": last_time_diff / mean_time,
                f"{prefix}time_zscore": (last_time_diff - mean_time) / std_time,
            }
        )

        if len(time_diffs) >= 2:
            time_acceleration = (
                (time_diffs.iloc[-1] - time_diffs.iloc[-2]) / time_diffs.iloc[-2]
                if time_diffs.iloc[-2] > 0
                else 0
            )
            features[f"{prefix}time_acceleration"] = time_acceleration

    return features


def cal_price(df: pd.DataFrame, prefix: str = "") -> dict:
    """Price movement and spread features"""
    features = {}
    mid = (df["bid"] + df["ask"]) / 2
    spread = df["ask"] - df["bid"]
    changes = mid.diff()

    if len(mid) >= 2:
        price_change = changes.iloc[-1]
        avg_change = changes.abs().mean() or 1

        features.update(
            {
                f"{prefix}price_change": price_change * 10000,
                f"{prefix}relative_change": price_change / avg_change,
                f"{prefix}spread": spread.iloc[-1],
                f"{prefix}spread_change": (spread.iloc[-1] - spread.iloc[-2]) * 10000,
            }
        )

        if len(mid) >= 3:
            prev_changes = changes.iloc[-3:-1].abs().mean() or 1
            breakthrough = abs(price_change) / prev_changes
            features[f"{prefix}breakthrough"] = breakthrough

    return features


def cal_pressure(df: pd.DataFrame, prefix: str = "") -> dict:
    """Buying vs selling pressure from bid/ask changes"""
    features = {}

    if len(df) >= 2:
        ask_change = df["ask"].diff().iloc[-1]
        bid_change = df["bid"].diff().iloc[-1]
        total_change = abs(ask_change) + abs(bid_change)

        features.update(
            {
                f"{prefix}buy_pressure": ask_change / total_change
                if total_change > 0
                else 0,
                f"{prefix}sell_pressure": abs(bid_change) / total_change
                if total_change > 0
                else 0,
            }
        )

    return features


def cal_volatility(df: pd.DataFrame, prefix: str = "") -> dict:
    """Volatility and momentum features"""
    features = {}
    mid = (df["bid"] + df["ask"]) / 2

    if len(mid) >= 3:
        window_changes = mid.diff().iloc[-3:]
        features.update(
            {
                f"{prefix}volatility": window_changes.std() * 10000,
                f"{prefix}price_momentum": window_changes.sum() * 10000,
                f"{prefix}direction_consistency": (
                    np.sign(window_changes) == np.sign(window_changes.iloc[-1])
                ).mean(),
            }
        )

    return features


def cal_breakthrough(df: pd.DataFrame, prefix: str = "") -> dict:
    """Multi-window breakthrough strength (price change / rolling std)"""
    features = {}
    mid = (df["bid"] + df["ask"]) / 2
    changes = mid.diff()

    if len(mid) >= 4:
        for window in [2, 3, 4]:
            window_std = changes.rolling(window).std().iloc[-1] or 1
            current_change = abs(changes.iloc[-1])
            features[f"{prefix}breakthrough_{window}"] = current_change / window_std

        breakthrough_consistency = np.sign(changes).rolling(3).sum().iloc[-1]
        features[f"{prefix}breakthrough_consistency"] = abs(breakthrough_consistency)

    return features


def cal_tick_density(df: pd.DataFrame, prefix: str = "") -> dict:
    """Tick frequency (ticks per second) for different windows"""
    features = {}

    for window in [3, 5, 10]:
        window_seconds = (df.index[-1] - df.index[-window:][0]).total_seconds()
        tick_density = window / window_seconds if window_seconds > 0 else 0
        features[f"{prefix}tick_density_{window}"] = tick_density

    if len(df) >= 6:
        current_density = 3 / (df.index[-1] - df.index[-3:][0]).total_seconds()
        prev_density = 3 / (df.index[-4] - df.index[-6:][0]).total_seconds()
        density_change = (
            (current_density - prev_density) / prev_density if prev_density > 0 else 0
        )
        features[f"{prefix}density_change"] = density_change

    return features


def cal_pos(df: pd.DataFrame, prefix: str = "") -> dict:
    """Aggregate all feature types for a given position"""
    features = {}
    features.update(cal_time(df, prefix))
    features.update(cal_price(df, prefix))
    features.update(cal_pressure(df, prefix))
    features.update(cal_volatility(df, prefix))
    features.update(cal_breakthrough(df, prefix))
    features.update(cal_tick_density(df, prefix))
    return features


def cal_features(df: pd.DataFrame, n: int = 5) -> dict:
    """Calculate features for last N tick positions to avoid lookahead bias"""
    features = {}
    for i in range(1, n + 1):
        current_df = df.iloc[: -i + 1] if i > 1 else df
        pos_features = cal_pos(current_df, f"pos_{i}_")
        features.update(pos_features)
    return features


train_evaluate_model(param_space)
