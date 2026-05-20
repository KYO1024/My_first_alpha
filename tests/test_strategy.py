from __future__ import annotations

import pandas as pd

from theme_second_wave.dashboard import render_discord_summary, render_markdown
from theme_second_wave.models import ScanResult, ScoreBreakdown, StockCandidate, WaveStage
from theme_second_wave.strategy import ThemeSecondWaveAnalyzer


def test_repair_setup_is_classified_as_repair() -> None:
    bars = _sample_bars()
    candidate = StockCandidate(code="000001", name="测试股", theme="AI", theme_score=80)
    result = ThemeSecondWaveAnalyzer(min_history_days=60).analyze(candidate, bars)
    assert result.stage in {WaveStage.REPAIR, WaveStage.SECOND_WAVE_CONFIRMED}
    assert result.score >= 50


def test_markdown_escapes_table_pipes() -> None:
    result = ScanResult(
        candidate=StockCandidate(code="000001", name="测试|股", theme="AI|算力"),
        stage=WaveStage.WATCH,
        score=10.0,
        breakdown=ScoreBreakdown(),
    )

    markdown = render_markdown([result])

    assert "测试\\|股" in markdown
    assert "AI\\|算力" in markdown


def test_discord_summary_uses_list_for_missing_data() -> None:
    result = ScanResult(
        candidate=StockCandidate(code="603881", name="数据港", theme="数据中心"),
        stage=WaveStage.DATA_MISSING,
        score=0.0,
        breakdown=ScoreBreakdown(),
        risks=["failed to load daily bars"],
    )

    summary = render_discord_summary([result])

    assert "| 排名 |" not in summary
    assert "1. 603881 数据港" in summary
    assert "原因: failed to load daily bars" in summary


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
