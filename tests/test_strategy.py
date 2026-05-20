from __future__ import annotations

import pandas as pd

from theme_second_wave.models import StockCandidate, WaveStage
from theme_second_wave.strategy import ThemeSecondWaveAnalyzer


def test_repair_setup_is_classified_as_repair() -> None:
    bars = _sample_bars()
    candidate = StockCandidate(code="000001", name="测试股", theme="AI", theme_score=80)
    result = ThemeSecondWaveAnalyzer(min_history_days=60).analyze(candidate, bars)
    assert result.stage in {WaveStage.REPAIR, WaveStage.SECOND_WAVE_CONFIRMED}
    assert result.score >= 50


def _sample_bars() -> pd.DataFrame:
    rows = []
    price = 10.0
    for i in range(45):
        price *= 1.004
        rows.append(_row(i, price, 1000000 + i * 1000))
    for i in range(45, 58):
        price *= 1.035
        rows.append(_row(i, price, 2500000))
    for i in range(58, 76):
        price *= 0.993
        rows.append(_row(i, price, 900000))
    for i in range(76, 82):
        price *= 1.012
        rows.append(_row(i, price, 1400000))
    return pd.DataFrame(rows)


def _row(day: int, close: float, volume: int) -> dict[str, object]:
    return {
        "date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=day),
        "open": close * 0.99,
        "high": close * 1.02,
        "low": close * 0.98,
        "close": close,
        "volume": volume,
    }
