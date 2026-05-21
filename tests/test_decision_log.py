from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from theme_second_wave.decision_log import update_decision_log
from theme_second_wave.models import ScanResult, ScoreBreakdown, StockCandidate, WaveStage


def test_decision_log_adds_focus_signal(tmp_path: Path) -> None:
    result = _result(
        current_price=100.0,
        latest_date="2026-05-21",
        stage=WaveStage.REPAIR,
    )

    summary = update_decision_log(
        results=[result],
        report_dir=tmp_path,
        generated_at=datetime(2026, 5, 21, 15, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert summary.added_count == 1
    assert summary.updated_count == 0
    assert summary.open_count == 1
    assert summary.jsonl_path.exists()
    assert summary.markdown_path.exists()
    assert "603881" in summary.markdown_path.read_text(encoding="utf-8")


def test_decision_log_updates_outcomes_on_later_scan(tmp_path: Path) -> None:
    first = _result(current_price=100.0, latest_date="2026-05-21", stage=WaveStage.REPAIR)
    update_decision_log(
        results=[first],
        report_dir=tmp_path,
        generated_at=datetime(2026, 5, 21, 15, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    later = _result(current_price=106.0, latest_date="2026-05-24", stage=WaveStage.SECOND_WAVE_CONFIRMED)
    summary = update_decision_log(
        results=[later],
        report_dir=tmp_path,
        generated_at=datetime(2026, 5, 24, 15, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    content = summary.jsonl_path.read_text(encoding="utf-8")

    assert summary.updated_count >= 3
    assert '"1d": {"asof": "2026-05-24", "return_pct": 6.0' in content
    assert '"3d": {"asof": "2026-05-24", "return_pct": 6.0' in content
    assert '"hit_trigger": true' in content


def _result(*, current_price: float, latest_date: str, stage: WaveStage) -> ScanResult:
    return ScanResult(
        candidate=StockCandidate(code="603881", name="数据港", theme="数据中心"),
        stage=stage,
        score=66.0,
        breakdown=ScoreBreakdown(),
        current_price=current_price,
        trigger_price=105.0,
        invalidation_price=92.0,
        metrics={
            "trigger_distance_pct": round((105.0 / current_price - 1.0) * 100.0, 2),
            "latest_date": latest_date,
            "data_source": "yfinance",
        },
        reasons=["候选池已标注主题/板块", "价格守住 MA20"],
        risks=["回撤不充分，容易高位震荡"],
    )
