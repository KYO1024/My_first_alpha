from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from .indicators import normalize_ohlcv


class MarketDataError(RuntimeError):
    pass


class MarketDataProvider:
    def __init__(self, data_dir: str | Path | None = None):
        env_dir = os.getenv("MARKET_DATA_DIR")
        self.data_dir = Path(data_dir or env_dir).expanduser() if (data_dir or env_dir) else None

    def get_daily(self, code: str, days: int = 120) -> pd.DataFrame:
        if self.data_dir:
            local = self._load_local_csv(code)
            if local is not None:
                return _tail_with_attrs(local, days)
        try:
            return self._load_online(code, days=days)
        except Exception as exc:
            raise MarketDataError(f"failed to load daily bars for {code}: {exc}") from exc

    def _load_local_csv(self, code: str) -> pd.DataFrame | None:
        if self.data_dir is None:
            return None
        candidates = [
            self.data_dir / f"{code}.csv",
            self.data_dir / f"{_to_prefixed_a_share(code)}.csv",
            self.data_dir / f"{_to_suffix_a_share(code)}.csv",
        ]
        for path in candidates:
            if path.exists():
                return _with_source(normalize_ohlcv(pd.read_csv(path)), f"local_csv:{path.name}")
        return None

    def _load_online(self, code: str, days: int) -> pd.DataFrame:
        if _is_a_share(code):
            try:
                return _load_akshare_daily(code, days)
            except Exception as akshare_exc:
                try:
                    return _load_yfinance_daily(_to_yfinance_a_share(code), days)
                except Exception as yfinance_exc:
                    raise MarketDataError(
                        f"akshare failed: {akshare_exc}; yfinance failed: {yfinance_exc}"
                    ) from yfinance_exc
        return _load_yfinance_daily(code, days)


def _is_a_share(code: str) -> bool:
    return code.isdigit() and len(code) == 6


def _to_prefixed_a_share(code: str) -> str:
    if not _is_a_share(code):
        return code
    return f"SH{code}" if code.startswith(("5", "6", "9")) else f"SZ{code}"


def _to_suffix_a_share(code: str) -> str:
    if not _is_a_share(code):
        return code
    return f"{code}.SH" if code.startswith(("5", "6", "9")) else f"{code}.SZ"


def _to_yfinance_a_share(code: str) -> str:
    if not _is_a_share(code):
        return code
    return f"{code}.SS" if code.startswith(("5", "6", "9")) else f"{code}.SZ"


def _load_akshare_daily(code: str, days: int) -> pd.DataFrame:
    import akshare as ak

    raw = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
    if raw is None or raw.empty:
        raise MarketDataError("akshare returned empty data")
    raw = raw.rename(
        columns={
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
        }
    )
    return _with_source(normalize_ohlcv(raw).tail(days).reset_index(drop=True), "akshare")


def _load_yfinance_daily(code: str, days: int) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(
        code,
        period=f"{max(days, 90)}d",
        interval="1d",
        auto_adjust=False,
        progress=False,
    )
    if raw is None or raw.empty:
        raise MarketDataError("yfinance returned empty data")
    raw = _flatten_yfinance_frame(raw).reset_index()
    raw.columns = [_flatten_yfinance_column(col) for col in raw.columns]
    raw = raw.rename(
        columns={
            "Date": "date",
            "Datetime": "date",
            "index": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    return _with_source(normalize_ohlcv(raw).tail(days).reset_index(drop=True), "yfinance")


def _with_source(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    frame.attrs["source"] = source
    return frame


def _tail_with_attrs(frame: pd.DataFrame, days: int) -> pd.DataFrame:
    trimmed = frame.tail(days).reset_index(drop=True)
    trimmed.attrs.update(frame.attrs)
    return trimmed


def _flatten_yfinance_frame(frame: pd.DataFrame) -> pd.DataFrame:
    flattened = frame.copy()
    flattened.columns = [_flatten_yfinance_column(col) for col in flattened.columns]
    return flattened


def _flatten_yfinance_column(column: object) -> str:
    if not isinstance(column, tuple):
        return str(column)

    known = {
        "date": "Date",
        "datetime": "Datetime",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "adj close": "Adj Close",
        "volume": "Volume",
    }
    for part in column:
        key = str(part).strip().lower()
        if key in known:
            return known[key]
    return "_".join(str(part).strip() for part in column if str(part).strip())
