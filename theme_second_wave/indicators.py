from __future__ import annotations

import pandas as pd


REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    frame.columns = [str(col).strip().lower() for col in frame.columns]
    aliases = {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
    }
    frame = frame.rename(columns=aliases)
    missing = [col for col in REQUIRED_COLUMNS if col not in frame.columns]
    if missing:
        raise ValueError(f"missing OHLCV columns: {missing}")

    frame = frame.loc[:, list(REQUIRED_COLUMNS)].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    for col in ("open", "high", "low", "close", "volume"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.dropna(subset=["date", "open", "high", "low", "close"])
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    return frame.reset_index(drop=True)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    frame = normalize_ohlcv(df)
    frame["pct_chg"] = frame["close"].pct_change() * 100
    for window in (5, 10, 20, 60):
        frame[f"ma{window}"] = frame["close"].rolling(window).mean()
    frame["vol_ma5"] = frame["volume"].rolling(5).mean()
    frame["vol_ma20"] = frame["volume"].rolling(20).mean()
    frame["high_20"] = frame["high"].rolling(20).max()
    frame["low_20"] = frame["low"].rolling(20).min()
    return frame


def safe_pct(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return (numerator / denominator - 1.0) * 100.0
