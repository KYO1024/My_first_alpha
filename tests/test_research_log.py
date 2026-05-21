from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from theme_second_wave.models import ScanConfig, ScanResult, ScoreBreakdown, StockCandidate, WaveStage
from theme_second_wave.research_log import build_run_card, write_run_card


def test_run_card_records_strategy_context(tmp_path: Path) -> None:
    watchlist = tmp_path / "watch_list.xlsx"
    pd.DataFrame([{"股票代码": "603881", "股票名称": "数据港", "行业": "数据中心"}]).to_excel(
        watchlist,
        index=False,
    )
    hypotheses = tmp_path / "hypotheses.json"
    hypotheses.write_text(
        """
{
  "strategy_version": "test_v1",
  "hypotheses": [
    {"id": "h1", "name": "数据中心修复", "themes": ["数据中心"]}
  ]
}
""".strip(),
        encoding="utf-8",
    )
    result = ScanResult(
        candidate=StockCandidate(code="603881", name="数据港", theme="数据中心"),
        stage=WaveStage.REPAIR,
        score=60.0,
        breakdown=ScoreBreakdown(),
        current_price=40.0,
        trigger_price=42.0,
        invalidation_price=36.0,
        metrics={
            "trigger_distance_pct": 5.0,
            "latest_date": "2026-05-21",
            "data_source": "yfinance",
        },
    )

    card = build_run_card(
        results=[result],
        config=ScanConfig(report_dir=tmp_path),
        watchlist_path=watchlist,
        candidate_count=1,
        dashboard_path=tmp_path / "latest_dashboard.md",
        csv_path=tmp_path / "latest_results.csv",
        hypotheses_path=hypotheses,
        generated_at=datetime(2026, 5, 21, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert card["strategy_version"] == "test_v1"
    assert card["watchlist"]["candidate_count"] == 1
    assert card["result_count"] == 1
    assert card["stage_counts"]["分歧修复"] == 1
    assert card["data_source_counts"] == {"yfinance": 1}
    assert card["hypotheses"]["matches"][0]["matched_count"] == 1
    assert card["focus"][0]["trigger_distance_pct"] == 5.0


def test_write_run_card_creates_latest_file(tmp_path: Path) -> None:
    watchlist = tmp_path / "watch_list.xlsx"
    watchlist.write_bytes(b"watchlist")

    latest = write_run_card(
        results=[],
        config=ScanConfig(report_dir=tmp_path),
        watchlist_path=watchlist,
        candidate_count=0,
        dashboard_path=tmp_path / "latest_dashboard.md",
        csv_path=tmp_path / "latest_results.csv",
        hypotheses_path=tmp_path / "missing.json",
    )

    assert latest == tmp_path / "latest_run_card.json"
    assert latest.exists()
