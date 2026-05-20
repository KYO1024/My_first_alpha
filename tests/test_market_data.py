from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

from theme_second_wave import market_data
from theme_second_wave.indicators import REQUIRED_COLUMNS
from theme_second_wave.market_data import MarketDataProvider


def test_a_share_online_loader_falls_back_to_yfinance(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    expected = pd.DataFrame({"close": [1.0]})

    def fail_akshare(code: str, days: int) -> pd.DataFrame:
        calls.append(f"ak:{code}")
        raise RuntimeError("akshare unavailable")

    def load_yfinance(code: str, days: int) -> pd.DataFrame:
        calls.append(f"yf:{code}")
        return expected

    monkeypatch.setattr(market_data, "_load_akshare_daily", fail_akshare)
    monkeypatch.setattr(market_data, "_load_yfinance_daily", load_yfinance)

    result = MarketDataProvider()._load_online("603881", days=120)

    assert result is expected
    assert calls == ["ak:603881", "yf:603881.SS"]


def test_yfinance_loader_accepts_multiindex_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    dates = pd.date_range("2026-01-01", periods=3)
    columns = pd.MultiIndex.from_tuples(
        [
            ("Open", "603881.SS"),
            ("High", "603881.SS"),
            ("Low", "603881.SS"),
            ("Close", "603881.SS"),
            ("Volume", "603881.SS"),
        ],
        names=["Price", "Ticker"],
    )
    raw = pd.DataFrame(
        [
            [10.0, 11.0, 9.8, 10.5, 1000],
            [10.5, 11.2, 10.1, 11.0, 1200],
            [11.0, 11.8, 10.8, 11.6, 1500],
        ],
        index=pd.Index(dates, name="Date"),
        columns=columns,
    )

    class FakeYFinance:
        @staticmethod
        def download(*args: object, **kwargs: object) -> pd.DataFrame:
            return raw

    monkeypatch.setitem(sys.modules, "yfinance", FakeYFinance)

    result = market_data._load_yfinance_daily("603881.SS", days=3)

    assert list(result.columns) == list(REQUIRED_COLUMNS)
    assert result["close"].tolist() == [10.5, 11.0, 11.6]
    assert result.attrs["source"] == "yfinance"


def test_local_csv_source_survives_tail(tmp_path: Path) -> None:
    csv_path = tmp_path / "603881.csv"
    pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=4),
            "open": [1, 2, 3, 4],
            "high": [1, 2, 3, 4],
            "low": [1, 2, 3, 4],
            "close": [1, 2, 3, 4],
            "volume": [100, 200, 300, 400],
        }
    ).to_csv(csv_path, index=False)

    result = MarketDataProvider(tmp_path).get_daily("603881", days=2)

    assert len(result) == 2
    assert result.attrs["source"] == "local_csv:603881.csv"
