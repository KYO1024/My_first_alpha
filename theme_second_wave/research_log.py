from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .dashboard import STAGE_LABELS, sort_results
from .models import ScanConfig, ScanResult, WaveStage


DEFAULT_HYPOTHESES_PATH = Path("config/hypotheses.json")


def write_run_card(
    *,
    results: list[ScanResult],
    config: ScanConfig,
    watchlist_path: Path,
    candidate_count: int,
    dashboard_path: Path,
    csv_path: Path,
    decision_log_summary: dict[str, object] | None = None,
    hypotheses_path: Path = DEFAULT_HYPOTHESES_PATH,
) -> Path:
    report_dir = Path(config.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    run_card = build_run_card(
        results=results,
        config=config,
        watchlist_path=watchlist_path,
        candidate_count=candidate_count,
        dashboard_path=dashboard_path,
        csv_path=csv_path,
        decision_log_summary=decision_log_summary,
        hypotheses_path=hypotheses_path,
        generated_at=now,
    )
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    run_card_path = report_dir / f"run_card_{timestamp}.json"
    latest_path = report_dir / "latest_run_card.json"
    payload = json.dumps(run_card, ensure_ascii=False, indent=2)
    run_card_path.write_text(payload + "\n", encoding="utf-8")
    latest_path.write_text(payload + "\n", encoding="utf-8")
    return latest_path


def build_run_card(
    *,
    results: list[ScanResult],
    config: ScanConfig,
    watchlist_path: Path,
    candidate_count: int,
    dashboard_path: Path,
    csv_path: Path,
    decision_log_summary: dict[str, object] | None = None,
    hypotheses_path: Path = DEFAULT_HYPOTHESES_PATH,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(ZoneInfo("Asia/Shanghai"))
    ordered = sort_results(results)
    hypotheses = _load_hypotheses(hypotheses_path)
    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "strategy_version": hypotheses.get("strategy_version", "theme_second_wave_v0.2"),
        "watchlist": {
            "path": str(watchlist_path),
            "sha256": _sha256_file(watchlist_path),
            "candidate_count": candidate_count,
        },
        "result_count": len(ordered),
        "config": {
            "min_history_days": config.min_history_days,
            "max_results": config.max_results,
            "data_dir": str(config.data_dir) if config.data_dir else None,
            "send_discord": config.send_discord,
        },
        "outputs": {
            "dashboard": str(dashboard_path),
            "csv": str(csv_path),
            "run_card": str(Path(config.report_dir) / "latest_run_card.json"),
            "decision_log": decision_log_summary.get("jsonl_path") if decision_log_summary else None,
            "decision_log_markdown": decision_log_summary.get("markdown_path") if decision_log_summary else None,
        },
        "decision_log": decision_log_summary or {},
        "stage_counts": _stage_counts(ordered),
        "data_source_counts": _metric_counts(ordered, "data_source"),
        "latest_date_counts": _metric_counts(ordered, "latest_date"),
        "hypotheses": {
            "path": str(hypotheses_path),
            "sha256": _sha256_file(hypotheses_path),
            "matches": _hypothesis_matches(ordered, hypotheses),
        },
        "focus": _focus_rows(ordered),
    }


def _stage_counts(results: list[ScanResult]) -> dict[str, int]:
    counts = Counter(item.stage for item in results)
    return {
        STAGE_LABELS[stage]: counts.get(stage, 0)
        for stage in (
            WaveStage.SECOND_WAVE_CONFIRMED,
            WaveStage.REPAIR,
            WaveStage.FIRST_WAVE,
            WaveStage.WATCH,
            WaveStage.FAILED,
            WaveStage.DATA_MISSING,
        )
    }


def _metric_counts(results: list[ScanResult], key: str) -> dict[str, int]:
    counts = Counter(str(item.metrics.get(key) or "-") for item in results)
    return dict(sorted(counts.items()))


def _focus_rows(results: list[ScanResult]) -> list[dict[str, Any]]:
    focus_stages = {WaveStage.SECOND_WAVE_CONFIRMED, WaveStage.REPAIR, WaveStage.FIRST_WAVE}
    rows = []
    for item in results:
        if item.stage not in focus_stages:
            continue
        rows.append(
            {
                "code": item.candidate.code,
                "name": item.candidate.name,
                "theme": item.candidate.theme,
                "sector": item.candidate.sector,
                "stage": STAGE_LABELS[item.stage],
                "score": item.score,
                "current_price": item.current_price,
                "trigger_price": item.trigger_price,
                "trigger_distance_pct": item.metrics.get("trigger_distance_pct"),
                "invalidation_price": item.invalidation_price,
                "latest_date": item.metrics.get("latest_date"),
                "data_source": item.metrics.get("data_source"),
                "action": item.action,
            }
        )
    return rows[:10]


def _load_hypotheses(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"strategy_version": "theme_second_wave_v0.2", "hypotheses": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _hypothesis_matches(results: list[ScanResult], registry: dict[str, Any]) -> list[dict[str, Any]]:
    matches = []
    for hypothesis in registry.get("hypotheses", []):
        themes = [str(item).lower() for item in hypothesis.get("themes", [])]
        matched = []
        for result in results:
            candidate_text = " ".join(
                part
                for part in (result.candidate.theme, result.candidate.sector, result.candidate.name)
                if part
            ).lower()
            if any(theme and theme.lower() in candidate_text for theme in themes):
                matched.append(
                    {
                        "code": result.candidate.code,
                        "name": result.candidate.name,
                        "stage": STAGE_LABELS[result.stage],
                        "score": result.score,
                        "trigger_distance_pct": result.metrics.get("trigger_distance_pct"),
                    }
                )
        matches.append(
            {
                "id": hypothesis.get("id"),
                "name": hypothesis.get("name"),
                "matched_count": len(matched),
                "matched_candidates": matched,
            }
        )
    return matches


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
