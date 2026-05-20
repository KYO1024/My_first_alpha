from __future__ import annotations

import pandas as pd
import pytest

from theme_second_wave import market_data
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
